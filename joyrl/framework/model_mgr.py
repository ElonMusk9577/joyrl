#!/usr/bin/env python
# coding=utf-8
'''
Author: JiangJi
Email: johnjim0816@gmail.com
Date: 2023-12-02 15:02:30
LastEditor: JiangJi
LastEditTime: 2023-12-02 23:19:01
Discription: 
'''
import time
import ray
from ray.util.queue import Queue as RayQueue
import threading
import torch
from typing import Dict, List
from queue import Queue
from joyrl.framework.message import Msg, MsgType
from joyrl.algos.base.policies import BasePolicy
from joyrl.framework.config import MergedConfig
from joyrl.framework.base import Moduler

class ModelMgr(Moduler):
    ''' model manager
    '''
    def __init__(self, cfg: MergedConfig, *args, **kwargs) -> None:
        super().__init__(cfg, *args, **kwargs)
        self.logger = kwargs['logger']
        self._latest_model_params_dict = {0: kwargs['model_params']}
        self._saved_model_que = RayQueue(maxsize = 128) if self.use_ray else Queue(maxsize = 128)
        
    def _t_start(self):
        self._t_save_policy = threading.Thread(target=self._save_policy)
        self._t_save_policy.setDaemon(True)
        self._t_save_policy.start()

    def init(self):
        if self.use_ray:
            self.logger.info.remote(f"[ModelMgr] Start model manager!")
        else:
            self.logger.info(f"[ModelMgr] Start model manager!")
        self._t_start()  
    
    def pub_msg(self, msg: Msg):
        ''' publish message
        '''
        msg_type, msg_data = msg.type, msg.data
        if msg_type == MsgType.MODEL_MGR_PUT_MODEL_PARAMS:
            self._put_model_params(msg_data)
        elif msg_type == MsgType.MODEL_MGR_GET_MODEL_PARAMS:
            return self._get_model_params()
        else:
            raise NotImplementedError
        

    def _put_model_params(self, msg_data):
        ''' put model params
        '''
        update_step, model_params = msg_data
        if update_step >= list(self._latest_model_params_dict.keys())[-1]:
            self._latest_model_params_dict[update_step] = model_params
        if update_step % self.cfg.model_save_fre == 0:
            while not self._saved_model_que.full(): # if queue is full, wait for 0.01s
                self._saved_model_que.put((update_step, model_params))
                time.sleep(0.001)
                break

    def _get_model_params(self):
        ''' get policy
        '''
        return list(self._latest_model_params_dict.values())[-1]

    def _save_policy(self):
        ''' async run
        '''
        while True:
            while not self._saved_model_que.empty():
                update_step, model_params = self._saved_model_que.get()
                torch.save(model_params, f"{self.cfg.model_dir}/{update_step}")
            time.sleep(0.05)
    


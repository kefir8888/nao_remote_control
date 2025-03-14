# -*- coding: utf-8 -*-
from modalities.modality import GetPoints
from modalities.skeleton_modalities import  Skeleton_3D
from collections import deque
import numpy as np
import common
import torch
from pose_estimation.draw import Plotter3d, draw_poses
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pose_estimation.one_euro_filter import OneEuroFilter
# from adam_sender import *

import torch
import torch.nn as nn

import io

import json
import os

import cv2

import pyrealsense2 as rs
import math

from modalities.modality import  Modality

class LSTM(nn.Module):

    def __init__(self,input_dim,hidden_dim,output_dim,layer_num):
        super(LSTM,self).__init__()
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.lstm = torch.nn.LSTM(input_dim,hidden_dim,layer_num,batch_first=True)
        self.fc = torch.nn.Linear(hidden_dim,output_dim)
        self.bn = nn.BatchNorm1d(32)

    def forward(self,inputs):
        x = self.bn(inputs)
        lstm_out,(hn,cn) = self.lstm(x)
        out = self.fc(lstm_out[:,-1,:])
        return out


def categoryFromOutput(output):
    LABELS = [
    "head",
    "clapping",
    "Pick",
    "point",
    "stend",
    "sit"
]
    top_n, top_i = output.topk(1)
    category_i = top_i[0].item()
    return LABELS[category_i], category_i


class RealSense (GetPoints):
    def __init__ (self, video_path_ = "", model_path_ = "", mode_ = "GPU", base_height_ = 512, logger_ = 0, focal_length = 1.93):
        GetPoints.__init__(self, logger_, model_path_, mode_, base_height_, focal_length, [], [])
        self.skel_3d = Skeleton_3D(logger_ = self.logger)
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
        self.config.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)
        self.align = rs.align(rs.stream.color)
        self.canvas_3d = np.zeros((848, 480, 3), dtype=np.uint8)
        self.plotter = Plotter3d(self.canvas_3d.shape[:2], origin=(0.5, 0.5), scale=0.1)
        self.counter = 0
        self.file = open('/home/kompaso/NAO_PROJECT/wenhai/source/modalities/data_test', 'w')
        self.count = 0
        self.filter = OneEuroFilter(freq=30, beta=0.01)
        self.joints_framework = ['neck', 'nose', 'mid_hip',
                 'l_sho', 'l_elb',
                 'l_wri', 'l_hip',
                 'l_knee', 'l_ank',
                 'r_sho', 'r_elb',
                 'r_wri', 'r_hip',
                 'r_kne', 'r_ank',
                 'r_eye', 'l_eye',
                 'r_ear', 'l_ear']


        self.joints_framework_in_work = ['nose','l_sho', 'l_elb','l_wri','r_sho','r_elb', 'r_wri', 'l_hip','l_knee','l_ank','r_hip','r_kne','r_ank','neck']

######################################################################
        # n_hidden = 128
        # n_joints = 14*3
        # n_layer = 3
        # self.for_recon = []
        # self.device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
        # # rnn = LSTM(n_joints,n_hidden,n_categories,n_layer)
        #
        # n_categories = 6
        # self.model = LSTM(n_joints,n_hidden,n_categories,n_layer)
        # self.model.load_state_dict(torch.load("/home/kompaso/diplom_modules/RNN-for-Human-Activity-Recognition-using-2D-Pose-Input-master/clap_sit_hop_stand.pth"))
        # self.model.to(self.device)
        # self.model.eval()


        if (video_path_ == ""):
            self.all_data = rs.pipeline()
            self.profile = self.all_data.start(self.config)

        self.read = False

    def name(self):
        return "RealSense"





    def _read_data (self):
        if (self.read == False):
            frames = self.all_data.wait_for_frames()
            aligned_frames = self.align.process(frames)
            self.img = np.asanyarray(aligned_frames.get_color_frame().get_data())
            depth_img = np.asanyarray(aligned_frames.get_depth_frame().get_data(), dtype=float)
            # max = float(depth_img.max()))

            xy_cords, _, edges = self._infer_net(self.img)
            if xy_cords != []:
                xy_cords_ = xy_cords.reshape(-1,2)

                coords_3D = np.zeros((xy_cords_.shape[0], 3))
                coords_3D[:,:2] = np.asarray(xy_cords_)
                coords_3D = coords_3D.astype(int)
                for i in range(xy_cords_.shape[0]):
                    if coords_3D[i,1] >= 480:
                        coords_3D[i,2] = self.filter(int(depth_img[479, coords_3D[i,0]]))
                    elif coords_3D[i,0] < 0:
                        coords_3D[i,2] = 0
                    else:
                        coords_3D[i,2] = self.filter(int(depth_img[coords_3D[i,1], coords_3D[i,0]]))

                if abs(coords_3D[5,1] - coords_3D[4,1]) <= 30 and abs(coords_3D[5,0] - coords_3D[4,0]) <= 30 and abs(coords_3D[5,1] - coords_3D[3,1]) <= 30 and abs(coords_3D[5,0] - coords_3D[3,0]) <= 30:
                    coords_3D[3,2] = coords_3D[0,2]
                    coords_3D[4,2] = int((coords_3D[3,2] + coords_3D[5,2])/2)

                if abs(coords_3D[5,1] - coords_3D[0,1]) <= 15 and abs(coords_3D[5,0] - coords_3D[0,0]) <= 15 :
                    coords_3D[0,2] = int((coords_3D[3,2] + coords_3D[9,2])/2)

                if abs(coords_3D[5,1] - coords_3D[3,1]) <= 30 and abs(coords_3D[5,0] - coords_3D[3,0]) <= 30 :
                    coords_3D[3,2] = coords_3D[0,2]

                if abs(coords_3D[5,1] - coords_3D[4,1]) <= 30 and abs(coords_3D[5,0] - coords_3D[4,0]) <= 30 :
                    coords_3D[4,2] = coords_3D[3,2]


    #################################################################################################3
                if abs(coords_3D[11,1] - coords_3D[10,1]) <= 30 and abs(coords_3D[11,0] - coords_3D[10,0]) <= 30 and abs(coords_3D[11,1] - coords_3D[9,1]) <= 30 and abs(coords_3D[11,0] - coords_3D[9,0]) <= 30:
                    coords_3D[9,2] = coords_3D[0,2]
                    coords_3D[10,2] = int((coords_3D[3,2] + coords_3D[11,1])/2)

                if abs(coords_3D[11,1] - coords_3D[0,1]) <= 15 and abs(coords_3D[11,0] - coords_3D[0,0]) <= 15 :
                    coords_3D[0,2] = int((coords_3D[9,2] + coords_3D[3,2])/2)

                if abs(coords_3D[11,1] - coords_3D[9,1]) <= 30 and abs(coords_3D[11,0] - coords_3D[9,0]) <= 30 :
                    coords_3D[9,2] = coords_3D[0,2]

                if abs(coords_3D[11,1] - coords_3D[10,1]) <= 30 and abs(coords_3D[11,0] - coords_3D[10,0]) <= 30 :
                    coords_3D[10,2] = coords_3D[9,2]

                if coords_3D[13,0] <= 0:
                    coords_3D[13][0] =coords_3D[12][0]
                    coords_3D[13][1] =coords_3D[12][1] + 90
                    coords_3D[13][2] =coords_3D[12][2]

                if coords_3D[7,0] <= 0:
                    coords_3D[7][0] =coords_3D[6][0]
                    coords_3D[7][1] =coords_3D[6][1] + 90
                    coords_3D[7][2] =coords_3D[6][2]

                if coords_3D[14,0] <= 0:
                    coords_3D[14][0] = coords_3D[12][0]
                    coords_3D[14][1] = coords_3D[12][1] + 180
                    coords_3D[14][2] = coords_3D[12][2]

                if coords_3D[8,0] <= 0:
                    coords_3D[8][0] = coords_3D[6][0]
                    coords_3D[8][1] = coords_3D[6][1] + 180
                    coords_3D[8][2] = coords_3D[6][2]



                print("CORDS:", len(coords_3D))
                print("STOP")

                # def normalization(frame_, joint_index=5, z_invers = False):
                #     frame = frame_.copy()
                #     frame = frame - frame[joint_index]
                #     t_frame = np.array(frame.T, dtype = float)
                #     max_x = max((t_frame[0].max(), -t_frame[0].min()))
                #     max_y = max((t_frame[1].max(), -t_frame[1].min()))
                #     max_z = max((t_frame[2].max(), -t_frame[2].min()))
                #     t_frame_ = np.zeros(())
                #
                #
                #
                #     if max_x != 0:
                #         t_frame[0] = np.array(t_frame[0], dtype = float)/max_x
                # #         print(t_frame[0])
                #     if max_y != 0:
                #         t_frame[1] = np.array(t_frame[1], dtype = float)/max_y
                #     if max_z != 0:
                #         t_frame[2] = np.array(t_frame[2], dtype = float)/max_z
                #
                #
                #     if z_invers == True:
                #         t_frame[0] = - t_frame[0]
                #         t_frame[1] = - t_frame[1]
                #         t_frame[2] = t_frame[2]
                #
                #     new_frame = t_frame.T
                #     return new_frame
                #
                #
                # def simplification(frame, joints_names , joints_in_work):
                #     dict_new = {}
                #     test_dict = dict(zip(joints_names, frame))
                #     for  x in joints_in_work:
                #         dict_new[x] = test_dict[x]
                #     new_frame = np.array(list(dict_new.values()))
                #     return new_frame

                # frame_rec_ = simplification(coords_3D, self.joints_framework, self.joints_framework_in_work)
                # frame_rec = normalization(frame_rec_)
                # self.for_recon.append(frame_rec.flatten())



                # if len(self.for_recon) == 16:
                #     # print(frame_rec)
                #     for_rec_array = np.array(self.for_recon)
                #     tensor_X_test = torch.from_numpy(np.array([for_rec_array])).float().to(self.device)
                #     # print(tensor_X_test.size())
                #     res = self.model(tensor_X_test)
                #     # print(res)
                #
                #     self.for_recon = []
                #     self.logger.update("Ares", categoryFromOutput(res))
                #
                if self.count < 128:
                    self.count+=1
                    for i in coords_3D.flatten():
                        self.file.write(str(i)+str(' '))
                if self.count == 128:
                    print("RECORD STOPED")
                    exit(0)
                    self.file.close()


                # print("RS", coords_3D)
                # self.plotter.plot(self.canvas_3d, coords_3D, edges)
                # cv2.imshow("kek", self.canvas_3d)
                # self.logger.update("l_wriz", coords_3D[11,2])
                # self.logger.update("l_elbz", coords_3D[10,2])
                # self.logger.update("l_shoz", coords_3D[9,2])
                #
                # self.logger.update("l_wriy", coords_3D[11,1])
                # self.logger.update("l_elby", coords_3D[10,1])
                # # self.logger.update("l_shoy", coords_3D[3,1])
                #
                # self.logger.update("l_wrix", coords_3D[11,0])
                # self.logger.update("l_elbx", coords_3D[10,0])
                # self.logger.update("l_shox", coords_3D[3,0])

                self.read_data = coords_3D


    def _process_data(self):
        self.skel_3d.read_data = self.read_data
        self.skel_3d._process_data()
        self.processed_data = self.skel_3d.processed_data






        # print("Realsense", self.processed_data)

        # self.processed_data = self.skel_3d.processed_data


    def _interpret_data(self):
        self.interpreted_data = self.processed_data

    def _get_command(self):
        commands = []

        # if (self.timeout.timeout_passed ()):
        for key in self.processed_data.keys():
            commands.append(("/set_joint_angle", [key, str(self.processed_data[key])]))
        # print("COMM", commands)

        # else:
        #     commands.append (("noaction", [""]))

        return commands

    def get_command(self, skip_reading_data=False):
        if (skip_reading_data == False):
            self._read_data()

        self._process_data()
        self._interpret_data()
        return self._get_command()

    def draw(self, img):
        return [self.canvas_3d, self.frame]

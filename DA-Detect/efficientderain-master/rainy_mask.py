from glob import glob
import os
import cv2
import numpy as np
import argparse
import random
import numpy as np
import cv2
import math
import torch
from torch.utils.data import Dataset
from torchvision import transforms

import augment_and_mix
import utils
import pdb
from tqdm import tqdm, trange



def resize_city(cityscapes_path, multi_weather_city_path,data_type='train'):
    # all_gt_paths = glob(os.path.join(cityscapes_path,'*',data_type,'*','*.png'),recursive=False)
    all_gt_paths = glob(os.path.join(cityscapes_path, data_type,'*.jpg'),recursive=False)
    # print("check",all_gt_paths)
    # pdb.set_trace()
    for path in tqdm(all_gt_paths):
        info = path.split(os.path.sep)
        # new_path = os.path.join(multi_weather_city_path, 'Cityscapes_overcast', info[-4], info[-3], info[-2], info[-1])
        # new_path = os.path.join(multi_weather_city_path, 'BDD100K_overcast', info[-3], info[-2], info[-1])
        # pdb.set_trace()
        new_path = os.path.join(multi_weather_city_path, 'BDD100K_overcast',info[-1])
        dir_path = os.path.dirname(new_path)
        gt = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
            except OSError:
                print("Creation of the directory %s failed" % dir_path)
        cv2.imwrite(new_path,gt)


def random_setecter(rain_path):
    '''
    Descripttion:
    return: random rain mask image each times
    '''
    files= os.listdir(rain_path)
    order_files = sorted(files,reverse=False)

    random_id = random.randint(0, len(order_files)-1)
    rain_img = cv2.imread(os.path.join(rain_path,order_files[random_id]))
    # print(str(order_files[random_id]))
    return rain_img


class RandomCrop(object):
    def __init__(self, image_size, crop_size):
        self.ch, self.cw = crop_size
        ih, iw = image_size

        self.h1 = random.randint(0, ih - self.ch)
        self.w1 = random.randint(0, iw - self.cw)

        self.h2 = self.h1 + self.ch
        self.w2 = self.w1 + self.cw

    def __call__(self, img):
        if len(img.shape) == 3:
            return img[self.h1: self.h2, self.w1: self.w2, :]
        else:
            return img[self.h1: self.h2, self.w1: self.w2]


def getRainLayer2(rand_id1, rand_id2,rain_mask):

    rainlayer_rand = rain_mask

    size = (2048,1024)
    size = (1280,720)
    
    rainlayer_rand = cv2.resize(rainlayer_rand, size)
    rainlayer_rand = rainlayer_rand.astype(np.float32) / 255.0
    rainlayer_rand = cv2.cvtColor(rainlayer_rand, cv2.COLOR_BGR2RGB)
    # pdb.set_trace()

    return rainlayer_rand


def getRandRainLayer2(rain_mask):
    rand_id1 = random.randint(1, 165)
    rand_id2 = random.randint(4, 8)
    rainlayer_rand = getRainLayer2(rand_id1, rand_id2,rain_mask)
    return rainlayer_rand



def reconstruct_condition(img_overcast, img_diff):
    img_recon = img_diff + img_overcast - 255
    img_recon = img_recon.astype(np.uint8)
    return img_recon


def rain_aug(img_gt, img_rainy,rain_mask):
    img_rainy = (img_rainy.astype(np.float32)) / 255.0
    img_gt = (img_gt.astype(np.float32)) / 255.0
    # if random.randint(0, 10) > 3:
    #     img_rainy_ret = img_rainy
    # else:
    #     img_rainy_ret = img_gt
    # img_gt_ret = img_gt
    img_rainy_ret = img_gt

    rainlayer_rand2 = getRandRainLayer2(rain_mask)
    # pdb.set_trace()
    rainlayer_aug2 = augment_and_mix.augment_and_mix(rainlayer_rand2, severity = 3, width = 3, depth = -1) * 1
    # rainlayer_rand2ex = getRandRainLayer2()
    # rainlayer_aug2ex = augment_and_mix.augment_and_mix(rainlayer_rand2ex, severity = 3, width = 3, depth = -1) * 1

    # height = min(img_gt.shape[0], rainlayer_aug2.shape[0])
    # width = min(img_gt.shape[1], rainlayer_aug2.shape[1])
    height = 1024
    width = 2048
    # height = min(img_gt.shape[0], min(rainlayer_aug2.shape[0], rainlayer_aug2ex.shape[0]))
    # width = min(img_gt.shape[1], min(rainlayer_aug2.shape[1], rainlayer_aug2ex.shape[1]))
    
    # cropper = RandomCrop(rainlayer_aug2.shape[:2], (height, width))
    # rainlayer_aug2_crop = cropper(rainlayer_aug2)

    #cropper = RandomCrop(rainlayer_aug2ex.shape[:2], (height, width))
    # rainlayer_aug2ex_crop = cropper(rainlayer_aug2ex)
    #print(height, width, rainlayer_aug2_crop.shape, rainlayer_aug2ex_crop.shape)
    # rainlayer_aug2_crop = rainlayer_aug2_crop + rainlayer_aug2ex_crop

    # cropper = RandomCrop(img_gt_ret.shape[:2], (height, width))
    # img_rainy_ret = cropper(img_rainy_ret)
    # img_gt_ret = cropper(img_gt_ret)
    # img_rainy_ret = img_rainy_ret + rainlayer_aug2_crop - img_rainy_ret*rainlayer_aug2_crop
    # pdb.set_trace()
    img_rainy_ret = img_rainy_ret + rainlayer_aug2 - img_rainy_ret*rainlayer_aug2
    np.clip(img_rainy_ret, 0.0, 1.0)
    
    img_rainy_ret = img_rainy_ret * 255
    # img_gt_ret = img_gt_ret * 255
    
    #cv2.imwrite("./temp/temp.jpg", cv2.cvtColor(img_rainy_ret, cv2.COLOR_RGB2BGR))
    
    # return img_rainy_ret, img_gt_ret
    return img_rainy_ret




def save_recon_img(img_recon, img_recon_path_save):
    dir_path = os.path.dirname(img_recon_path_save)
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
        except OSError:
            print("Creation of the directory %s failed" % dir_path)
    cv2.imwrite(img_recon_path_save, cv2.cvtColor(img_recon, cv2.COLOR_RGB2BGR))


def get_city_conditions(mw_city_path,rain_mask_path,data_type):
    all_diff_paths_n = []
    all_diff_paths_nd = []
    all_diff_paths_s = []
    all_diff_paths_sd = []
    all_diff_paths_w = []
    all_diff_paths_wd = []
    all_paths_o = []
    # all_diff_paths_od = glob(os.path.join(mw_city_path, 'Cityscapes_overcast', '*', data_type, '*', '*.png'))
    # all_diff_paths_od = glob(os.path.join(mw_city_path, 'Cityscapes_overcast', 'leftImg8bit', data_type, '*.png'))
    all_diff_paths_od = glob(os.path.join(mw_city_path, 'BDD100K_overcast', '*.jpg'))
    # all_diff_paths_od = glob(os.path.join(mw_city_path, 'Cityscapes_overcast', 'leftImg8bit', 'train', 'bochum', '*.png'))
    # pdb.set_trace()

    # for p in all_diff_paths_od:
    #     all_diff_paths_n.append(p.replace('Cityscapes_overcast_drops','Cityscapes_night'))
    #     all_diff_paths_nd.append(p.replace('Cityscapes_overcast_drops','Cityscapes_night_drops'))
    #     all_diff_paths_s.append(p.replace('Cityscapes_overcast_drops','Cityscapes_snow'))
    #     all_diff_paths_sd.append(p.replace('Cityscapes_overcast_drops','Cityscapes_snow_drops'))
    #     all_diff_paths_w.append(p.replace('Cityscapes_overcast_drops','Cityscapes_wet'))
    #     all_diff_paths_wd.append(p.replace('Cityscapes_overcast_drops','Cityscapes_wet_drops'))
    # pdb.set_trace()
    for p in all_diff_paths_od:
        # prefix = os.path.join(mw_city_path,'Cityscapes_overcast','leftImg8bit',data_type)
        # prefix = os.path.join(mw_city_path,'BDD100K_overcast',data_type)
        prefix = os.path.join(mw_city_path,'BDD100K_overcast')
        info = p.split(os.sep)
        # pdb.set_trace()
        # all_paths_o.append(os.path.join(prefix,info[-2],info[-1]))
        all_paths_o.append(os.path.join(prefix,info[-1]))
    
    # pdb.set_trace()
    save_condition_with_rain_mask('BDD100K_overcast', all_paths_o, rain_mask_path)

    # save_condition('Cityscapes_night', all_paths_o, all_diff_paths_n)
    # save_condition('Cityscapes_night_drops', all_paths_o, all_diff_paths_nd)
    # save_condition('Cityscapes_snow', all_paths_o, all_diff_paths_s)
    # save_condition('Cityscapes_snow_drops', all_paths_o, all_diff_paths_sd)
    # save_condition('Cityscapes_wet', all_paths_o, all_diff_paths_w)
    # save_condition('Cityscapes_wet_drops', all_paths_o, all_diff_paths_wd)


def save_condition_with_rain_mask(condition_name, all_paths_o,rain_mask_path):


    for i in trange(len(all_paths_o)):

        img_o = cv2.imread(all_paths_o[i])


        #loading the rain mask
        rain_mask = random_setecter(rain_mask_path)        

        size = (1280,720)
        img_diff_o_cond = cv2.resize(rain_mask, size)

        img_o = cv2.cvtColor(img_o, cv2.COLOR_BGR2RGB)
        img_diff_o_cond = cv2.cvtColor(img_diff_o_cond, cv2.COLOR_BGR2RGB)

        # img_cond = reconstruct_condition(img_o, img_diff_o_cond)
        img_cond = rain_aug(img_o, img_diff_o_cond,rain_mask)

        cond_path = all_paths_o[i].replace('Cityscapes_overcast',condition_name)
        dir_path = os.path.dirname(cond_path)
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
            except OSError:
                print("Creation of the directory %s failed" % dir_path)
        save_recon_img(img_cond, cond_path)


if __name__ == "__main__":
    # parser = argparse.ArgumentParser()
    # parser.add_argument("-cityscapes_path", help="Path to Cityscapes dataset root")
    # # parser.add_argument("-city_diff_path", help="Path to where all difference images are saved")
    # parser.add_argument("-multi_weather_city_path", help="Path to multi weather city root")
    # args = parser.parse_args()
    # if not os.path.exists(args.multi_weather_city_path):
    #     try:
    #         os.makedirs(args.multi_weather_city_path)
    #     except OSError:
    #         print("Creation of the directory %s failed" % args.multi_weather_city_path)
    # resize_city(args.cityscapes_path, args.multi_weather_city_path)
    # # get_city_conditions(args.city_diff_path, args.multi_weather_city_path)
    # get_city_conditions(args.multi_weather_city_path)

    ### Path to raining maks root
    # rain_mask_path = '/home/jinlong/Desktop/final_heavyV1'
    rain_mask_path = '/home/jinlong/Desktop/rainy_mask/final_heavyV1'
    ### Path to Cityscapes dataset root
    cityscapes_path = '/home/jinlong/jinlong_NAS/Driving/dataset/BDD100K/daytime_clear_city_street_coco'
    ### Path to where all difference images are saved
    difference_path_img = '/home/jinlong/Desktop'

    # data_type = 'val' # 'train' or 'val' or 'test'
    # data_type_list = ['train','test','val']
    data_type_list = ['train']


    # for data_type in data_type_list:
    #     print('Processing {} data'.format(data_type))
    #     if not os.path.exists(difference_path_img):
    #         try:
    #             os.makedirs(difference_path_img)
    #         except OSError:
    #             print("Creation of the directory %s failed" % difference_path_img)
    #     resize_city(cityscapes_path, difference_path_img,data_type=data_type)

    for data_type in data_type_list:  
        print("start to add the raining masks: ",data_type)
        get_city_conditions(difference_path_img,rain_mask_path,data_type)

    # if not os.path.exists(difference_path_img):
    #     try:
    #         os.makedirs(difference_path_img)
    #     except OSError:
    #         print("Creation of the directory %s failed" % difference_path_img)
    # resize_city(cityscapes_path, difference_path_img,data_type=data_type)
    # get_city_conditions(difference_path_img,rain_mask_path,data_type)
    

# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
import torch
import torchvision

from maskrcnn_benchmark.structures.bounding_box import BoxList
from maskrcnn_benchmark.structures.segmentation_mask import SegmentationMask
from maskrcnn_benchmark.structures.keypoint import PersonKeypoints

from pycocotools.coco import COCO
from PIL import Image
import os

import pdb

min_keypoints_per_image = 10


def _count_visible_keypoints(anno):
    return sum(sum(1 for v in ann["keypoints"][2::3] if v > 0) for ann in anno)


def _has_only_empty_bbox(anno):
    return all(any(o <= 1 for o in obj["bbox"][2:]) for obj in anno)


def has_valid_annotation(anno):
    # if it's empty, there is no annotation
    if len(anno) == 0:
        return False
    # if all boxes have close to zero area, there is no annotation
    if _has_only_empty_bbox(anno):
        return False
    # keypoints task have a slight different critera for considering
    # if an annotation is valid
    if "keypoints" not in anno[0]:
        return True
    # for keypoint detection tasks, only consider valid images those
    # containing at least min_keypoints_per_image
    if _count_visible_keypoints(anno) >= min_keypoints_per_image:
        return True
    return False


class COCODataset(torchvision.datasets.coco.CocoDetection):
    def __init__(
        self, ann_file, root, remove_images_without_annotations, transforms=None, is_source= True
    ):
        super(COCODataset, self).__init__(root, ann_file)
        # sort indices for reproducible results
        self.ids = sorted(self.ids)

        # pdb.set_trace()

        # filter images without detection annotations
        if remove_images_without_annotations:
            ids = []
            for img_id in self.ids:
                ann_ids = self.coco.getAnnIds(imgIds=img_id, iscrowd=None)
                anno = self.coco.loadAnns(ann_ids)
                if has_valid_annotation(anno):
                    ids.append(img_id)
            self.ids = ids

        self.json_category_id_to_contiguous_id = {
            v: i + 1 for i, v in enumerate(self.coco.getCatIds())
        }
        self.contiguous_category_id_to_json_id = {
            v: k for k, v in self.json_category_id_to_contiguous_id.items()
        }
        self.id_to_img_map = {k: v for k, v in enumerate(self.ids)}
        self._transforms = transforms
        self.is_source = is_source

    def __getitem__(self, idx):
        img, anno = super(COCODataset, self).__getitem__(idx)
        # print('root: ', self.root)

        # filter crowd annotations
        # TODO: might be better to add an extra field
        anno = [obj for obj in anno if obj["iscrowd"] == 0]

        boxes = [obj["bbox"] for obj in anno]
        boxes = torch.as_tensor(boxes).reshape(-1, 4)  # guard against no boxes
        # print('boxes: ', boxes)
        target = BoxList(boxes, img.size, mode="xywh").convert("xyxy")

        classes = [obj["category_id"] for obj in anno]
        classes = [self.json_category_id_to_contiguous_id[c] for c in classes]
        classes = torch.tensor(classes)
        target.add_field("labels", classes)

        masks = [obj["segmentation"] for obj in anno]
        masks = SegmentationMask(masks, img.size)
        target.add_field("masks", masks)

        domain_labels = torch.ones_like(classes, dtype=torch.bool) if self.is_source else torch.zeros_like(classes, dtype=torch.bool)
        target.add_field("is_source", domain_labels)

        # print("classes: ", classes.size())
        # print("domain_labels: ", domain_labels.size()) # pdb.set_trace()
        # print("labels: ", domain_labels)

        if anno and "keypoints" in anno[0]:
            keypoints = [obj["keypoints"] for obj in anno]
            keypoints = PersonKeypoints(keypoints, img.size)
            target.add_field("keypoints", keypoints)

        target = target.clip_to_image(remove_empty=True)

        if self._transforms is not None:
            img, target = self._transforms(img, target)

        # print('path: ', os.path.join(self.root, self.coco.loadImgs(self.ids[idx])[0]['file_name']))
        # idx = [self.coco.loadImgs(self.ids[idx])[0]['file_name'], self.coco.getAnnIds(imgIds=self.ids[idx]), self.ids[idx]]
        # idx = [self.coco.loadImgs(self.ids[idx])[0]['file_name']]
  
        return img, target, idx

    # pdb.set_trace()

    def get_img_info(self, index):
        img_id = self.id_to_img_map[index]
        img_data = self.coco.imgs[img_id]
        return img_data


#TODO:jinlong for three datasets
class COCODataset_da(torchvision.datasets.coco.CocoDetection):


    """
    ann_file_set: ann_file_source, ann_file_positive, ann_file_negative

    root_set: root_source, root_target_positive, root_target_negative 
    
    """

    def __init__(
        self, ann_file, root, remove_images_without_annotations, _transforms=None, is_source= True
    ):
        super(COCODataset, self).__init__(root, ann_file)
        # sort indices for reproducible results
        self.ids = sorted(self.ids)

        # pdb.set_trace()

        # filter images without detection annotations
        if remove_images_without_annotations:
            ids = []
            for img_id in self.ids:
                ann_ids = self.coco.getAnnIds(imgIds=img_id, iscrowd=None)
                anno = self.coco.loadAnns(ann_ids)
                if has_valid_annotation(anno):
                    ids.append(img_id)
            self.ids = ids

        self.json_category_id_to_contiguous_id = {
            v: i + 1 for i, v in enumerate(self.coco.getCatIds())
        }
        self.contiguous_category_id_to_json_id = {
            v: k for k, v in self.json_category_id_to_contiguous_id.items()
        }
        self.id_to_img_map = {k: v for k, v in enumerate(self.ids)}
        self.transforms = _transforms
        self.is_source = is_source

    def __getitem__(self, idx):
        img, anno = super(COCODataset, self).__getitem__(idx)
        # print('root: ', self.root)

        # filter crowd annotations
        # TODO: might be better to add an extra field
        anno = [obj for obj in anno if obj["iscrowd"] == 0]

        boxes = [obj["bbox"] for obj in anno]
        boxes = torch.as_tensor(boxes).reshape(-1, 4)  # guard against no boxes
        # print('boxes: ', boxes)
        target = BoxList(boxes, img.size, mode="xywh").convert("xyxy")

        classes = [obj["category_id"] for obj in anno]
        classes = [self.json_category_id_to_contiguous_id[c] for c in classes]
        classes = torch.tensor(classes)
        target.add_field("labels", classes)

        masks = [obj["segmentation"] for obj in anno]
        masks = SegmentationMask(masks, img.size)
        target.add_field("masks", masks)

        domain_labels = torch.ones_like(classes, dtype=torch.bool) if self.is_source else torch.zeros_like(classes, dtype=torch.bool)
        target.add_field("is_source", domain_labels)

        if anno and "keypoints" in anno[0]:
            keypoints = [obj["keypoints"] for obj in anno]
            keypoints = PersonKeypoints(keypoints, img.size)
            target.add_field("keypoints", keypoints)

        target = target.clip_to_image(remove_empty=True)

        if self.transforms is not None:
            img, target = self.transforms(img, target)

        # pdb.set_trace()
        # print('img_ids: ',self.ids[idx], ' idx: ', idx, ' anno: ',len(anno))
        # print('path: ', os.path.join(self.root, self.coco.loadImgs(self.ids[idx])[0]['file_name']))
        # print('Boxlist: ', target.bbox[0])
        # print('')
        # print('')

        idx = [self.coco.loadImgs(self.ids[idx])[0]['file_name'], self.coco.getAnnIds(imgIds=self.ids[idx]), self.ids[idx]] 

        return img, target, idx

    # pdb.set_trace()

    def get_img_info(self, index):
        img_id = self.id_to_img_map[index]
        img_data = self.coco.imgs[img_id]
        return img_data
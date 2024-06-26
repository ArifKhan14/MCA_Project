# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
import datetime
import logging
import time
from cv2 import log
import os
import torch
import torch.distributed as dist
from maskrcnn_benchmark.utils.comm import get_world_size
from maskrcnn_benchmark.utils.metric_logger import MetricLogger
from tqdm import tqdm
import warnings
import pdb
import torch.multiprocessing
torch.multiprocessing.set_sharing_strategy('file_system')
import numpy as np
from maskrcnn_benchmark.config import cfg
from maskrcnn_benchmark.utils.miscellaneous import mkdir
from maskrcnn_benchmark.data import make_data_loader
from maskrcnn_benchmark.engine.inference import inference
from maskrcnn_benchmark.utils.comm import synchronize
import random

# import timm
# import timm.optim
# import timm.scheduler


def seed_torch(seed=1029):
    random.seed(seed)   
    np.random.seed(seed)  
    torch.manual_seed(seed)   
    torch.cuda.manual_seed(seed)  
    torch.cuda.manual_seed_all(seed)  # if you are using multi-GPU.  
    torch.backends.cudnn.benchmark = False   # if benchmark=True, deterministic will be False
    torch.backends.cudnn.deterministic = True  




def reduce_loss_dict(loss_dict):
    """
    Reduce the loss dictionary from all processes so that process with rank
    0 has the averaged results. Returns a dict with the same fields as
    loss_dict, after reduction.
    """
    world_size = get_world_size()
    if world_size < 2:
        return loss_dict
    with torch.no_grad():
        loss_names = []
        all_losses = []
        for k in sorted(loss_dict.keys()):
            loss_names.append(k)
            all_losses.append(loss_dict[k])
        all_losses = torch.stack(all_losses, dim=0)
        dist.reduce(all_losses, dst=0)
        if dist.get_rank() == 0:
            # only main process gets accumulated, so only divide by
            # world_size in this case
            all_losses /= world_size
        reduced_losses = {k: v for k, v in zip(loss_names, all_losses)}
    return reduced_losses


def do_train(
    model,
    data_loader,
    optimizer,
    scheduler,
    checkpointer,
    device,
    checkpoint_period,
    arguments,
):
    seed_torch()
    logger = logging.getLogger("maskrcnn_benchmark.trainer")
    logger.info("Start training")
    meters = MetricLogger(delimiter="  ")
    max_iter = len(data_loader)
    start_iter = arguments["iteration"]
    model.train()
    start_training_time = time.time()
    end = time.time()
    warnings.filterwarnings("ignore", category=UserWarning)
    for iteration, (images, targets, _) in enumerate(data_loader, start_iter):
        # pdb.set_trace()
        data_time = time.time() - end
        iteration = iteration + 1
        arguments["iteration"] = iteration

        scheduler.step()

        images = images.to(device)
        targets = [target.to(device) for target in targets]

        loss_dict = model(images, targets)

        losses = sum(loss for loss in loss_dict.values())

        # reduce losses over all GPUs for logging purposes
        loss_dict_reduced = reduce_loss_dict(loss_dict)
        losses_reduced = sum(loss for loss in loss_dict_reduced.values())
        meters.update(loss=losses_reduced, **loss_dict_reduced)

        optimizer.zero_grad()
        losses.backward()
        optimizer.step()

        batch_time = time.time() - end
        end = time.time()
        meters.update(time=batch_time, data=data_time)

        eta_seconds = meters.time.global_avg * (max_iter - iteration)
        eta_string = str(datetime.timedelta(seconds=int(eta_seconds)))

        if iteration % 20 == 0 or iteration == max_iter:
            logger.info(
                meters.delimiter.join(
                    [
                        "eta: {eta}",
                        "iter: {iter}",
                        "{meters}",
                        "lr: {lr:.6f}",
                        "max mem: {memory:.0f}",
                    ]
                ).format(
                    eta=eta_string,
                    iter=iteration,
                    meters=str(meters),
                    lr=optimizer.param_groups[0]["lr"],
                    memory=torch.cuda.max_memory_allocated() / 1024.0 / 1024.0,
                )
            )
        if iteration % checkpoint_period == 0:
            checkpointer.save("model_{:07d}".format(iteration), **arguments)
        if iteration == max_iter:
            checkpointer.save("model_final", **arguments)

    total_training_time = time.time() - start_training_time
    total_time_str = str(datetime.timedelta(seconds=total_training_time))
    logger.info(
        "Total training time: {} ({:.4f} s / it)".format(
            total_time_str, total_training_time / (max_iter)
        )
    )



def do_da_train(
    model,
    source_data_loader,
    positive_target_data_loader,
    negative_target_data_loader,
    data_loader_val, 
    optimizer,
    scheduler,
    checkpointer,
    device,
    checkpoint_period,
    arguments,
    cfg,
    distributed,
    meters,
    triplet_data_loading=True,
    triplet_data_aligned=True,
):
    
    eval_use_in_training = cfg.MODEL.EVAL_USE_IN_TRAINING
    seed_torch()

    logger = logging.getLogger("maskrcnn_benchmark.trainer")
    logger.info("Start training")
    # meters = MetricLogger(delimiter=" ")
    # max_iter = len(source_data_loader)
    max_iter = len(positive_target_data_loader)
    # start_iter = arguments["iteration"]
    start_iter = 0

    model.train()
    start_training_time = time.time()
    end = time.time()
    iou_types = ("bbox",)

    if triplet_data_loading: # load data from 3 dataloaders
        if triplet_data_aligned:

            training_dataloader = positive_target_data_loader 
            #[data_source, data_positive, data_negative]
        else:
            training_dataloader = zip(source_data_loader, positive_target_data_loader, negative_target_data_loader)
    else: # load data from 2 dataloaders

        training_dataloader = zip(source_data_loader, positive_target_data_loader)
 
    for iteration, iter_data in enumerate(training_dataloader, start_iter):
        

        data_time = time.time() - end
        arguments["iteration"] = iteration
        
        if triplet_data_loading:
            if triplet_data_aligned: # triplet data aligned
                source_images, source_targets, positive_target_images, positive_target_targets, negative_target_images, negative_target_targets,idx1, idx2, idx3 = iter_data ####the dataloader Dataset_triplet() can be found in data/build.py 
                # print("this code working-1!")
                # print("idx1: ", idx1)
                # print("idx2: ", idx2)
                # print("idx3: ", idx3)
            else: # triplet data not aligned
                source_images, source_targets, _ = iter_data[0]
                positive_target_images, positive_target_targets, _ = iter_data[1]
                negative_target_images, negative_target_targets, _= iter_data[2]
                # print("this code working-2!")

            images = (source_images + positive_target_images + negative_target_images).to(device)
            targets = [target.to(device) for target in list(source_targets + positive_target_targets + negative_target_targets)]

        else: # load data from 2 dataloaders
            # pdb.set_trace()
            source_images, source_targets, _ = iter_data[0]
            positive_target_images, positive_target_targets, _= iter_data[1]

            images = (source_images+positive_target_images).to(device)
            targets = [target.to(device) for target in list(source_targets+positive_target_targets)]

            # print("this code working-3!")

        loss_dict = model(images, targets)

        losses = sum(loss for loss in loss_dict.values())

        # reduce losses over all GPUs for logging purposes
        loss_dict_reduced = reduce_loss_dict(loss_dict)
        losses_reduced = sum(loss for loss in loss_dict_reduced.values())
        meters.update(loss=losses_reduced, **loss_dict_reduced)

        optimizer.zero_grad()
        losses.backward()
        optimizer.step()
        
        # scheduler.step()
        scheduler.step_update(iteration)

        batch_time = time.time() - end
        end = time.time()
        meters.update(time=batch_time, data=data_time)

        eta_seconds = meters.time.global_avg * (max_iter - iteration)
        eta_string = str(datetime.timedelta(seconds=int(eta_seconds)))

        if iteration % 20 == 0 or iteration == max_iter:
            logger.info(
                meters.delimiter.join(
                    [
                        "eta: {eta}",
                        "iter: {iter}",
                        "{meters}",
                        "lr: {lr:.6f}",
                        "max mem: {memory:.0f}",
                    ]
                ).format(
                    eta=eta_string,
                    iter=iteration,
                    meters=str(meters),
                    lr=optimizer.param_groups[0]["lr"],
                    memory=torch.cuda.max_memory_allocated() / 1024.0 / 1024.0,
                )
            )
        if iteration % checkpoint_period == 0:
            if iteration ==0:
                continue
            checkpointer.save("model_{:07d}".format(iteration), **arguments)

            print('cosine annealing is chosen for lr scheduler')
            epoch = int(iteration/checkpoint_period)
            scheduler.step(epoch)
        if iteration == max_iter-1:
            checkpointer.save("model_final", **arguments)
        if torch.isnan(losses_reduced).any():
            logger.critical('Loss is NaN, exiting...')
            return 

        if eval_use_in_training:

            if iteration % checkpoint_period == 0:
                if iteration ==0:
                    continue
                synchronize()
                with torch.no_grad():
                    if data_loader_val is not None and checkpoint_period > 0:
                        meters_val = MetricLogger(delimiter="  ")
                        
                        # pdb.set_trace()
                        _ = inference(  # The result can be used for additional logging, e. g. for TensorBoard
                            model,
                            # The method changes the segmentation mask format in a data loader,
                            # so every time a new data loader is created:
                            # make_data_loader(cfg, is_train=False, is_distributed=(get_world_size() > 1), is_for_period=True),
                            data_loader_val[0],
                            dataset_name="[Validation]",
                            iou_types=iou_types,
                            box_only=False if cfg.MODEL.RETINANET_ON else cfg.MODEL.RPN_ONLY,
                            device=cfg.MODEL.DEVICE,
                            expected_results=cfg.TEST.EXPECTED_RESULTS,
                            expected_results_sigma_tol=cfg.TEST.EXPECTED_RESULTS_SIGMA_TOL,
                            output_folder=None,
                        )
                        synchronize()
                        model.train()
                        logger.info(
                            meters_val.delimiter.join(
                                [
                                    "[Validation]: ",
                                    "eta: {eta}",
                                    "iter: {iter}",
                                    "{meters}",
                                    "lr: {lr:.6f}",
                                    "max mem: {memory:.0f}",
                                ]
                            ).format(
                                eta=eta_string,
                                iter=iteration,
                                meters=str(meters_val),
                                lr=optimizer.param_groups[0]["lr"],
                                memory=torch.cuda.max_memory_allocated() / 1024.0 / 1024.0,
                            )
                        )


    total_training_time = time.time() - start_training_time
    total_time_str = str(datetime.timedelta(seconds=total_training_time))
    logger.info(
        "Total training time: {} ({:.4f} s / it)".format(
            total_time_str, total_training_time / (max_iter)
        )
    )

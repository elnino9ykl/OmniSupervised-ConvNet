# OmniSupervised-ConvNet
Omni-Supervised Efficient ConvNet for Robust Semantic Segmentation

## Gardens Point Dataset with Pixel-Wise Traversable Area Annotations

### GoogleDrive
[**Download Link**](https://drive.google.com/file/d/1YDphc00nIeC9-x-JbiQ-gQ2cFv2LFiD0/view?usp=sharing), 600 images
### BaiduYun
[**Download Link**](https://pan.baidu.com/s/19cg1yWsvNuUNOgAa9kf4uQ), 600 Images

![Example segmentation](gardens_traversability.jpg?raw=true "Example segmentation")

## Code Usage
Training:
```
CUDA_VISIBLE_DEVICES=0,1,2,3
python3 segment.py
--basedir /home/kyang/Downloads/
--num-epochs 200
--batch-size 12
--savedir /erfpsp
--datasets 'MAP' 'IDD20K'
--num-samples 18000
--alpha 0
--beta 0
--model erfnet_pspnet
```

Evaluation:
```
python3 eval_color.py
--datadir /home/kyang/Downloads/Mapillary/
--subset val
--loadDir ./trained/
--loadWeights model_best.pth
--loadModel erfnet_pspnet.py
--basedir /home/kyang/Downloads/
--datasets 'MAP' 'IDD20K'
```


## Publications
If you use our dataset or code, please consider referencing any of the following papers:

**In Defense of Multi-Source Omni-Supervised Efficient ConvNet for Robust Semantic Segmentation in Heterogeneous Unseen Domains.**
K. Yang, X. Hu, K. Wang, R. Stiefelhagen.
In IEEE Intelligent Vehicles Symposium (**IV**), Las Vegas, NV, United States (Virtual), October 2020.
[[**PDF**](http://www.yangkailun.com/publications/iv2020_omnisupervision_kailun.pdf)]

**Unifying Terrain Awareness for the Visually Impaired through Real-Time Semantic Segmentation.**
K. Yang, K. Wang, L.M. Bergasa, E. Romera, W. Hu, D. Sun, J. Sun, R. Cheng, T. Chen, E. López.
Sensors, May 2018.
[[**PDF**](https://www.mdpi.com/1424-8220/18/5/1506)]

# ERF-PSPNet full model definition for Pytorch
# April 2019
# Kailun Yang
#######################

import torch
import torch.nn as nn
import torch.nn.init as init
import torch.nn.functional as F

import math

from erfnet_imagenet import ERFNet as ERFNet_imagenet

class DownsamplerBlock (nn.Module):
    def __init__(self, ninput, noutput):
        super().__init__()

        self.conv = nn.Conv2d(ninput, noutput-ninput, (3, 3), stride=2, padding=1, bias=True)
        self.pool = nn.MaxPool2d(2, stride=2)
        self.bn = BatchNorm(noutput, eps=1e-3)
        #self.bn = nn.BatchNorm2d(noutput, eps=1e-3)

    def forward(self, input):
        output = torch.cat([self.conv(input), self.pool(input)], 1)
        output = self.bn(output)
        return F.relu(output)
    
class non_bottleneck_1d (nn.Module):
    def __init__(self, chann, dropprob, dilated):       
        super().__init__()

        self.conv3x1_1 = nn.Conv2d(chann, chann, (3, 1), stride=1, padding=(1,0), bias=True)

        self.conv1x3_1 = nn.Conv2d(chann, chann, (1,3), stride=1, padding=(0,1), bias=True)

        self.bn1 = BatchNorm(chann, eps=1e-03)
        #self.bn1 = nn.BatchNorm2d(chann, eps=1e-03)

        self.conv3x1_2 = nn.Conv2d(chann, chann, (3, 1), stride=1, padding=(1*dilated,0), bias=True, dilation = (dilated,1))

        self.conv1x3_2 = nn.Conv2d(chann, chann, (1,3), stride=1, padding=(0,1*dilated), bias=True, dilation = (1, dilated))

        self.bn2 = BatchNorm(chann, eps=1e-03)
        #self.bn2 = nn.BatchNorm2d(chann, eps=1e-03)

        self.dropout = nn.Dropout2d(dropprob)
        

    def forward(self, input):

        output = self.conv3x1_1(input)
        output = F.relu(output)
        output = self.conv1x3_1(output)
        output = self.bn1(output)
        output = F.relu(output)

        output = self.conv3x1_2(output)
        output = F.relu(output)
        output = self.conv1x3_2(output)
        output = self.bn2(output)
       
        if (self.dropout.p != 0):
            output = self.dropout(output)
        
        return F.relu(output+input)    #+input = identity (residual connection)


class Encoder(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.initial_block = DownsamplerBlock(3,16)

        self.layers = nn.ModuleList()

        self.layers.append(DownsamplerBlock(16,64))

        for x in range(0, 5):    #5 times
           self.layers.append(non_bottleneck_1d(64, 0.03, 1))   

        self.layers.append(DownsamplerBlock(64,128))

        for x in range(0, 2):    #2 times
            self.layers.append(non_bottleneck_1d(128, 0.3, 2))
            self.layers.append(non_bottleneck_1d(128, 0.3, 4))
            self.layers.append(non_bottleneck_1d(128, 0.3, 8))
            self.layers.append(non_bottleneck_1d(128, 0.3, 16))

        self.output_conv = nn.Conv2d(128, num_classes, 1, stride=1, padding=0, bias=True)

    def forward(self, input, predict=False):
        output = self.initial_block(input)

        for layer in self.layers:
            output = layer(output)

        if predict:
            output = self.output_conv(output)

        return output


class UpsamplerBlock (nn.Module):
    def __init__(self, ninput, noutput):
        super().__init__()
        self.conv = nn.ConvTranspose2d(ninput, noutput, 3, stride=2, padding=1, output_padding=1, bias=True)
        self.bn = BatchNorm(noutput, eps=1e-3)
        #self.bn = nn.BatchNorm2d(noutput, eps=1e-3)

    def forward(self, input):
        output = self.conv(input)
        output = self.bn(output)
        return F.relu(output)

class FGlo(nn.Module):
    """
    the FGlo class is employed to refine the feature
    """
    def __init__(self, channel, reduction=16):
        super(FGlo, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
                nn.Linear(channel, channel // reduction),
                nn.ReLU(inplace=True),
                nn.Linear(channel // reduction, channel),
                nn.Sigmoid()
        )

    def forward(self, x):
        b, c, _, _ = x.size()
        y = self.avg_pool(x).view(b, c)
        y = self.fc(y).view(b, c, 1, 1)
        return x * y

class sSE(nn.Module):
    def __init__(self, in_channels):
        super().__init__()
        self.Conv1x1 = nn.Conv2d(in_channels, 1, kernel_size=1, bias=False)
        self.norm = nn.Sigmoid()

    def forward(self, U):
        q = self.Conv1x1(U)  # U:[bs,c,h,w] to q:[bs,1,h,w]
        q = self.norm(q)
        return U * q  # 广播机制

class cSE(nn.Module):
    def __init__(self, in_channels):
        super().__init__()
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.Conv_Squeeze = nn.Conv2d(in_channels, in_channels // 2, kernel_size=1, bias=False)
        self.Conv_Excitation = nn.Conv2d(in_channels // 2, in_channels, kernel_size=1, bias=False)
        self.norm = nn.Sigmoid()

    def forward(self, U):
        z = self.avgpool(U)# shape: [bs, c, h, w] to [bs, c, 1, 1]
        z = self.Conv_Squeeze(z) # shape: [bs, c/2]
        z = self.Conv_Excitation(z) # shape: [bs, c]
        z = self.norm(z)
        return U * z.expand_as(U)

class scSE(nn.Module):
    def __init__(self, in_channels):
        super().__init__()
        self.cSE = cSE(in_channels)
        self.sSE = sSE(in_channels)

    def forward(self, U):
        U_sse = self.sSE(U)
        U_cse = self.cSE(U)
        return U_cse+U_sse

class PSPDec(nn.Module):

    def __init__(self, in_features, out_features, downsize, upsize=(64,128)):
        super(PSPDec,self).__init__()
        
        self.F_scSE=scSE(out_features)

        self.features = nn.Sequential(
            nn.AvgPool2d(downsize, stride=downsize),
            nn.Conv2d(in_features, out_features, 1, bias=False),
            BatchNorm(out_features, momentum=.95),
            #nn.BatchNorm2d(out_features, momentum=.95),
            nn.ReLU(inplace=True)
            #nn.Upsample(size=upsize, mode='bilinear')
        )
        self.ups = nn.Upsample(size=upsize, mode='bilinear')

    def forward(self, x):
        x = self.features(x)
        x = self.F_scSE(x)
        x = self.ups(x)
        
        return x

class Decoder (nn.Module):
    def __init__(self, num_classes):
        super().__init__()

        self.layer5a = PSPDec(128, 32, (64,128),(64,128))
        self.layer5b = PSPDec(128, 32, (32,64),(64,128))
        self.layer5c = PSPDec(128, 32, (16,32),(64,128))
        self.layer5d = PSPDec(128, 32, (8,16),(64,128))

        self.final = nn.Sequential(
            nn.Conv2d(256, 256, 3, padding=1, bias=False),
            BatchNorm(256, momentum=.95),
            #nn.BatchNorm2d(256, momentum=.95),
            nn.ReLU(inplace=True),
            nn.Dropout(.1),
            #nn.Conv2d(256, num_classes, 1),
        )

    def forward(self, x):
        #x=x[0]
        
        x = self.final(torch.cat([
            x,
            self.layer5a(x),
            self.layer5b(x),
            self.layer5c(x),
            self.layer5d(x),
        ], 1))

        return x

class Decoder1 (nn.Module):
    def __init__(self, num_classes):
        super().__init__()

        self.layer = nn.Conv2d(256,num_classes, 1)

    def forward(self, x):
        #x=x[0]
        
        x = self.layer(x)
        return x

class Decoder2 (nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x):
        return F.upsample(x,size=(512,1024), mode='bilinear') #train resolution: 512x1024

#ERF-PSPNet
class ERFPSPNet(nn.Module):
    def __init__(self, num_classes, encoder=None):  #use encoder to pass pretrained encoder
        super().__init__()

        if (encoder == None):
            self.encoder = Encoder(num_classes)
        else:
            self.encoder = encoder

        self.decoder = Decoder(num_classes)
        self.decoder1 = Decoder1(num_classes)
        self.decoder2 = Decoder2()
        self.out_dim = 256

    def forward(self, input, only_encode=False):
        if only_encode:
            return self.encoder.forward(input, predict=True)
        else:
            output = self.encoder(input)    #predict=False by default
            output = self.decoder(output)
            output = self.decoder1(output)
            return self.decoder2.forward(output)

def fill_up_weights(up):
	w = up.weight.data
	f = math.ceil(w.size(2) / 2)
	c = (2 * f - 1 - f % 2) / (2. * f)
	for i in range(w.size(2)):
		for j in range(w.size(3)):
			w[0, 0, i, j] = \
				(1 - math.fabs(i / f - c)) * (1 - math.fabs(j / f - c))
	for c in range(1, w.size(0)):
		w[c, 0, :, :] = w[0, 0, :, :]

class Net(nn.Module):

	def __init__(self, classes, embed_dim, resnet, pretrained_model=None,
				 pretrained=True, use_torch_up=False):
		super().__init__()
		assert(isinstance(classes , dict)), f"num_labels should be dict, got {type(classes)}"
		self.datasets = list(classes.keys())
		self.embed_dim = embed_dim
        
		pretrainedEnc = torch.nn.DataParallel(ERFNet_imagenet(1000))
		pretrainedEnc.load_state_dict(torch.load("erfnet_encoder_pretrained.pth.tar")['state_dict'])
		pretrainedEnc = next(pretrainedEnc.children()).features.encoder

		model = ERFPSPNet(num_classes=1000, encoder=pretrainedEnc)  #Add decoder to encoder
		pmodel = nn.DataParallel(model)
		#pmodel = pmodel.cuda()

		self.base = nn.Sequential(*list(model.children())[:-2]) ## Encoder. 
		#self.base = model[:-2]
		self.seg = nn.ModuleList() ## Decoder 1d conv
		self.up = nn.ModuleList() ## Decoder upsample (non-trainable)
	
		for n_labels in classes.values():
			m = nn.Conv2d(model.out_dim, n_labels, kernel_size=1, bias=True)
			n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
			m.weight.data.normal_(0, math.sqrt(2. / n))
			m.bias.data.zero_()
			self.seg.append(m)

			if use_torch_up:
				self.up.append(nn.UpsamplingBilinear2d(scale_factor=8))
			else:
				up = nn.ConvTranspose2d(n_labels, n_labels, 16, stride=8, padding=4,
										output_padding=0, groups=n_labels,
										bias=False)
				fill_up_weights(up)
				up.weight.requires_grad = False
				self.up.append(up)

		## Encoder output module
		m = nn.Conv2d(model.out_dim , self.embed_dim , kernel_size=1, bias=True)
		n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
		m.weight.data.normal_(0, math.sqrt(2. / n))
		m.bias.data.zero_()
		self.en_map = m
		self.en_up = nn.ConvTranspose2d(self.embed_dim , self.embed_dim , 16, stride=8, padding=4
													,output_padding=0,groups=self.embed_dim, bias=False)
		
		fill_up_weights(self.en_up)
		self.en_up.weight.requires_grad = False

	def forward(self, x, enc=True, finetune=False):

		y_encoder = self.base(x)

		if finetune:
			y_encoder = y_encoder.detach()
		
		output_dict = {key:None for key in self.datasets}
		for seg_layer , up_layer , key in zip(self.seg , self.up , self.datasets):
			y = seg_layer(y_encoder)
			y = up_layer(y)
			#y = F.upsample(y,size=(540,960), mode='bilinear')
			output_dict[key] = y

		if enc:
			y_encoder = self.en_map(y_encoder)
			y_encoder = self.en_up(y_encoder)
			return output_dict , y_encoder
		else:
			return output_dict


	def optim_parameters(self, memo=None):
		for param in self.base.parameters():
			yield param
		for param in self.seg.parameters():
			yield param
		for param in self.en_map.parameters():
			yield param

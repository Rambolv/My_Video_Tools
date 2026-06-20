import torch
from .IFNet_HDv3 import *

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class Model:
    def __init__(self, local_rank=-1):
        self.flownet = IFNet()
        self.device()
        self.version = 3.9

    def train(self):
        self.flownet.train()

    def eval(self):
        self.flownet.eval()

    def device(self):
        self.flownet.to(device)

    def load_model(self, path, rank=0):
        def convert(param):
            if rank == -1:
                return {k.replace("module.", ""): v for k, v in param.items() if "module." in k}
            return param
        if rank <= 0:
            pkl = '{}/flownet.pkl'.format(path)
            sd = convert(torch.load(pkl, map_location='cpu'))
            self.flownet.load_state_dict(sd, strict=False)

    def inference(self, img0, img1, timestep=0.5, scale=1.0):
        imgs = torch.cat((img0, img1), 1)
        scale_list = [8/scale, 4/scale, 2/scale, 1/scale]
        flow, mask, merged = self.flownet(imgs, timestep, scale_list)
        return merged[3]

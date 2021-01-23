import torch
from torch import Tensor
import torch.nn as nn
from torchvision import models

def initialize_model():
    """
    Initialize a Resnet model from pytorch,
    not pretrained and adjusted to work on our dataset

    Returns
    -------
    Resnet18: Cnn model     
    """
    model = models.resnet18(pretrained=False)
    model.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, 25)
    
    return model


if __name__ == "__main__":
    model = initialize_model()
    torch.save(model, "../saved_models/resnet.pt")
    print("Model created and saved in: " + " ../saved_models/resnet.pt")
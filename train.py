import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter
from torch import optim
from torch.optim import lr_scheduler

import copy
import argparse
import os

import sign_language_mnist
import utils
from models import cnn_model, simple_cnn, resnet, squeezenet

SAVE_MODEL_DIR = "saved_models"

MODELS = {
    "cnn_model": cnn_model.CNN(),
    "simple_cnn": simple_cnn.Net(),
    "resnet": resnet.initialize_model(),
    "squeezenet": squeezenet.initialize_model(),
}


def get_args_parser():
    parser = argparse.ArgumentParser(description="Model training")
    parser.add_argument("--config", type=str, default="config.yaml", help="Config file path")
    parser.add_argument(
        "-m", "--model", type=str, default="cnn_model", choices=MODELS.keys(), help="Model to be trained"
    )
    return parser


def train(
    model, dataloaders, criterion, optimizer, device, writer, scheduler=None, save=True, num_epochs=25, plot=True
):
    """
    Training process

    Parameters
    ----------
    model : nn.Module
        Model to be trained
    dataloaders : dict[str, torch.utils.data.DataLoader]
        Dictionary containing training and validation dataloaders
    criterion :
        Loss function
    optimizer : torch.optim.Optimizer
        Optimization algorithms
    device : torch.device
        Device for training
    writer : torch.utils.tensorboard.SummaryWriter
        SummaryWriter which writes data to tensorboard
    scheduler : torch.optim.lr_scheduler, optional
        Learning rate scheduler, by default None
    save : bool, optional
        Save the best trained model, by default True
    num_epochs : int, optional
        Number of training epochs, by default 25
    plot : bool, optional
        Plotting training loss and accuracy, by default True

    Returns
    -------
    nn.Module
        The best trained model
    """
    print(f"Start training {model.__class__.__name__}")

    best_model_wts = copy.deepcopy(model.state_dict())
    best_acc = 0.0

    # for plotting
    train_val_loss = {x: list() for x in ["train", "val"]}
    train_val_acc = {x: list() for x in ["train", "val"]}

    # for TensorBoard
    train_val_loss_dict = dict()
    train_val_acc_dict = dict()

    for epoch in range(1, num_epochs + 1):
        print(f"Epoch {epoch}")
        print("-" * 10)

        for phase in ["train", "val"]:
            if phase == "train":
                model.train()
            else:
                model.eval()

            running_loss = 0.0
            running_corrects = 0
            running_true_corrects = 0.0
            running_predicted = 0.0

            for images, labels in dataloaders[phase]:
                images = images.to(device)
                labels = labels.to(device)

                optimizer.zero_grad()

                # forward
                # track history if only in training phase
                with torch.set_grad_enabled(phase == "train"):
                    outputs = model(images)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)

                    # backward + optimize only in trianing phase
                    if phase == "train":
                        loss.backward()
                        optimizer.step()

                # statistics
                running_loss += loss.item() * images.shape[0]
                running_corrects += torch.sum(preds == labels.data)

            if scheduler and phase == "train":
                scheduler.step()

            epoch_loss = running_loss / len(dataloaders[phase].dataset)
            train_val_loss[phase].append(epoch_loss)
            writer.add_scalar(f"Loss/{phase}", epoch_loss, epoch)

            epoch_acc = running_corrects.double() / len(dataloaders[phase].dataset)

            train_val_acc[phase].append(epoch_acc)
            writer.add_scalar(f"Accuracy/{phase}", epoch_acc, epoch)

            train_val_loss_dict.update({phase: epoch_loss})
            train_val_acc_dict.update({phase: epoch_acc})

            print(f"{phase} Loss: {epoch_loss:.4f}, Acc: {epoch_acc:.4f}")

            # deep copy model weights if new best model occurs
            if phase == "val" and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())
                print("New best model!")

        writer.add_scalars("Loss: Train vs. Val", train_val_loss_dict, epoch)
        writer.add_scalars("Accuracy: Train vs. Val", train_val_acc_dict, epoch)
        print()

    if plot:
        utils.plot_training(train_val_loss, train_val_acc)

    # load best model weights
    model.load_state_dict(best_model_wts)
    if save:
        if not os.path.exists(SAVE_MODEL_DIR):
            os.makedirs(SAVE_MODEL_DIR)
        model_path = f"{SAVE_MODEL_DIR}/{model.__class__.__name__}_best.pt"
        torch.save(model, model_path)
        print(f"Save model in {model_path}")

    return model


if __name__ == "__main__":
    arg_parser = get_args_parser()
    args = arg_parser.parse_args()

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Running on device: {device}")

    utils.set_random_seed(42)  # ensure reproducibility

    model = MODELS[args.model].to(device)
    dataloaders = sign_language_mnist.get_train_val_loaders()

    # Read hyperparameters from config file
    train_config = utils.get_config(args.config)["train"]
    EPOCHS = train_config["epochs"]
    LEARNING_RATE = train_config["learning_rate"]
    SAVE = train_config["save"]
    MOMENTUM = train_config["momentum"]
    LR_GAMMA = train_config["learning_rate_gamma"]
    STEP_SIZE = train_config["learning_rate_decay_period"]

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.SGD(model.parameters(), lr=LEARNING_RATE, momentum=MOMENTUM)
    exp_lr_scheduler = lr_scheduler.StepLR(optimizer, step_size=STEP_SIZE, gamma=LR_GAMMA)

    with SummaryWriter("runs/sign_language") as writer:
        train(
            model,
            dataloaders,
            criterion,
            optimizer,
            device,
            writer,
            scheduler=exp_lr_scheduler,
            save=SAVE,
            num_epochs=EPOCHS,
        )

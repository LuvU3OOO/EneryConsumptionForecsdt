import numpy as np
import torch
import torch.nn as nn
from dataset import train_loader, X_train, week_train_dataset, week_test_dataset, y_test, test_loader, batch_size
import os
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error
from math import sqrt
from sklearn.preprocessing import StandardScaler
import pandas as pd
import time
import datetime

# parameters
input_dim = X_train.shape[2]
n_seq = 7
batch_size = batch_size
output_dim = 1
hidden_dim = 128
n_epochs = 200
num_layers = 2
learning_rate = 1e-3
weight_decay = 1e-6
is_bidirectional = False
dropout_prob = 0.2
save_path = r'./models/rnnModel2.ckpt'
device = 'cuda:0' if torch.cuda.is_available() else 'cpu'

if is_bidirectional:
    D = 2
else:
    D = 1


class rnnModel(nn.Module):
    def __init__(self):
        super(rnnModel, self).__init__()

        # dimension for rnn or Birnn

        self.rnn = nn.RNN(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=is_bidirectional,
            dropout=dropout_prob,
        )

        self.fc = nn.Linear(hidden_dim * D, output_dim)

    def forward(self, x):
        hidden_0 = torch.zeros(D * num_layers, x.size(0), hidden_dim).to(device)

        output, h_n = self.rnn(x, hidden_0.detach())

        output = self.fc(output)

        return output


rnnNet = rnnModel().to(device)
criterion = torch.nn.MSELoss(reduction="mean")
optimizer = torch.optim.Adam(params=rnnNet.parameters(), lr=learning_rate, weight_decay=weight_decay)

train_losses = []


def train():
    for epoch in range(n_epochs):
        batch_losses = []
        for i, (inputs, label) in enumerate(train_loader):
            inputs, label = inputs.to(device), label.to(device)
            y_pred = rnnNet(inputs)
            loss = criterion(y_pred, label)
            batch_losses.append(loss.item())

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        train_loss = np.mean(batch_losses)
        train_losses.append(train_loss)

        if epoch == 0 or (epoch + 1) % 10 == 0:
            print(f'[{epoch + 1}/{n_epochs}] Training loss: {train_loss:.4f}')

    # 保存模型
    if not os.path.isdir('models'):
        os.mkdir('models')  # Create directory of saving models.
    torch.save(rnnNet.state_dict(), save_path)


def forecast(history, n_seq):
    history = np.array(history)
    data = history.reshape(-1, history.shape[2])

    # 检索输入数据的最后观测值
    input_x = data[-n_seq:, :]

    # reshape into [1, n_input, 1]
    input_x = input_x.reshape((1, input_x.shape[0], input_x.shape[1]))

    # forecast the nest week
    with torch.no_grad():
        pred = rnnNet(torch.Tensor(input_x).to(device))

    pred = pred.cpu().numpy()
    # print(pred.shape)
    # print(pred[0])
    return pred[0]


def evaluate_forecasts(actual, predicted):
    scores = list()
    if len(predicted.shape) > 2:
        predicted = predicted.squeeze(axis=2)

    # calculate an RMSE score for each day
    for i in range(actual.shape[1]):
        # calculate mse
        mse = mean_squared_error(actual[:, i], predicted[:, i])
        # calculate rmse
        rmse = sqrt(mse)
        # store
        scores.append(rmse)
    # calculate overall RMSE
    s = 0
    print(actual.shape, predicted.shape)
    print(actual[0,0])
    print(predicted[0][0])
    for row in range(actual.shape[0]):
        for col in range(actual.shape[1]):
            s += (actual[row, col] - predicted[row, col]) ** 2
    score = sqrt(s / (actual.shape[0] * actual.shape[1]))
    return score, scores


def evaluate_model(train, test, n_seq):
    # history is a list of weekly data
    history = [x_train for x_train in train]
    # walk-forward validation over each week
    predictions = list()
    for i in range(len(test)):
        # predict the week
        pred_sequence = forecast(history, n_seq)
        # store the predictions
        predictions.append(pred_sequence)
        # get real observation and add to history for predicting the next week
        history.append(test[i, :])
        # evaluate predictions days for each week
    predictions = np.array(predictions)
    score, scores = evaluate_forecasts(test[:, :, test.shape[2] - 1], predictions)
    return score, scores, predictions


def plot_losses():
    plt.plot(train_losses, label="Training loss")
    plt.legend()
    plt.title("Losses")
    plt.show()
    plt.close()


# summarize scores
def summarize_scores(name, score, scores):
    s_scores = ', '.join(['%.1f' % s for s in scores])
    print('%s: [%.3f] %s' % (name, score, s_scores))


# inverse transform to results
def inverse_transform(base_values, to_transform_values):
    scaler = StandardScaler()
    scaler.fit(base_values)
    new_values = scaler.inverse_transform(to_transform_values)
    return new_values


def format_predictions(predictions, values, idx_test):
    df_res = pd.DataFrame(data={"total_load_predicted_values": predictions,
                                "total_load_real_values": values}, index=idx_test)
    return df_res


def plot_multiple_time_series(index, real_values, predicted_values, name_model):
    plt.figure(figsize=(20, 10))
    plt.plot(index, real_values, ".-y", label="real", linewidth=2)
    plt.plot(index, predicted_values, ".-.r", label="predicted", linewidth=1)
    plt.legend()
    plt.xticks(rotation=45)
    plt.title(f"{name_model} - Real x Predicted 7 Days Load Forecast")
    plt.show()
    plt.close()


def subplots_time_series(index, real_values, predicted_values, name_model):
    fig, ax = plt.subplots(2, 1, sharex=True, figsize=(20, 10))
    ax[0].plot(index, real_values, ".-y", label="real", linewidth=1)
    ax[1].plot(index, predicted_values, ".-.r", label="predicted", linewidth=1)

    ax[0].legend()
    ax[1].legend()
    plt.xticks(rotation=45)
    plt.suptitle(f"{name_model} - Real and Predicted 7 Days Load Forecast")
    plt.show()
    plt.close()


def format_time(time):
    elapsed_rounded = int(round((time)))
    # 格式化为 hh:mm:ss
    return str(datetime.timedelta(seconds=elapsed_rounded))


predictions_by_model = []
t0 = time.time()
# train()
t1 = time.time()
training_time = t1 - t0
training_time = format_time(training_time)
print('rnn training time:', training_time)
plot_losses()
score, scores, predictions = evaluate_model(week_train_dataset, week_test_dataset, n_seq)
predictions_by_model.append(predictions)
summarize_scores('rnnNet', score, scores)
pred_rnn_values = predictions_by_model[0].squeeze(2)
rnn_values = np.ravel(inverse_transform(y_test.values.reshape(-1, 1), pred_rnn_values))
print(rnn_values.shape)
print(rnn_values[:10])
df_rnn_values = format_predictions(rnn_values, y_test, y_test.index)
print(df_rnn_values.head())
subplots_time_series(df_rnn_values.index.to_list(), df_rnn_values["total_load_real_values"],
                     df_rnn_values["total_load_predicted_values"], "rnn")
plot_multiple_time_series(df_rnn_values.index.to_list(), df_rnn_values["total_load_real_values"],
                          df_rnn_values["total_load_predicted_values"], "rnn")



def record():
    # df = pd.DataFrame({'Rnn': train_losses})  # 创建dataframe
    # df1 = pd.DataFrame({'Rnn': df_rnn_values["total_load_predicted_values"]})  # 创建dataframe
    # df.to_csv(r'C:\D\PytorchProgect\pytorchrtest\EnergyForecast\data\loss\rnn.csv',index=False)
    # df1.to_csv(r'C:\D\PytorchProgect\pytorchrtest\EnergyForecast\data\pred\rnn.csv',index=False)
    df2 = pd.DataFrame({'real':  df_rnn_values["total_load_real_values"]})  # 创建dataframe
    df2.to_csv(r'C:\D\PytorchProgect\pytorchrtest\EnergyForecast\data\pred\real.csv',index=False)
# record()
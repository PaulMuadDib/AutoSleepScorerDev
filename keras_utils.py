# -*- coding: utf-8 -*-
import os, sys
import time
import keras
import tools
import pickle
import numpy as np
import matplotlib.pyplot as plt
from sklearn.utils import shuffle
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix, log_loss
from sklearn.model_selection import GroupKFold

#%%
def cv(data, targets, groups, modfun, epochs=250, folds=5, batch_size=1440,
       val_batch_size=0, stop_after=0, name='', counter=0, plot = False):
    """
    Crossvalidation routinge for training with a keras model.
    
    :param ...: should be self-explanatory

    :returns results: (val_acc, val_f1, test_acc, test_f1)
    """
    if val_batch_size == 0: val_batch_size = batch_size
    input_shape = (data.shape[1:]) #train_data.shape
    n_classes = targets.shape[1]
    
    print('Starting {} at {}'.format(modfun.__name__, time.ctime()))
    
    global results
    results =[]
    gcv = GroupKFold(folds)
    
    for i, idxs in enumerate(gcv.split(groups, groups, groups)):
        
        train_idx, test_idx = idxs
        sub_cv = GroupKFold(folds)
        train_sub_idx, val_idx = sub_cv.split(groups[train_idx], groups[train_idx], groups[train_idx]).__next__()
        val_idx      = train_idx[val_idx]  
        train_idx    = train_idx[train_sub_idx]
        
        train_data   = data[train_idx]
        train_target = targets[train_idx]
        val_data     = data[val_idx]
        val_target   = targets[val_idx]
        test_data    = data[test_idx]       
        test_target  = targets[test_idx]
        
        model = modfun(input_shape, n_classes)
        modelname = model.name
        cb = Checkpoint([val_data,val_target],verbose=1, counter=counter, 
                        epochs_to_stop=stop_after, plot = plot)
        model.fit(train_data,train_target, batch_size, epochs=epochs, verbose=0, callbacks=[cb])
        
        y_pred = model.predict(test_data, batch_size)
        y_true = test_target
        val_acc = cb.best_acc
        val_f1  = cb.best_f1
        test_acc = accuracy_score(np.argmax(y_pred,1),np.argmax(y_true,1))
        test_f1  = f1_score(np.argmax(y_pred,1),np.argmax(y_true,1), average="macro")
        
        confmat = confusion_matrix(np.argmax(y_pred,1),np.argmax(y_true,1))
        
        print('val acc/f1: {:.5f}/{:.5f}, test acc/f1: {:.5f}/{:.5f}'.format(cb.best_acc, cb.best_f1, test_acc, test_f1))
        save_dict = {'1 Number':counter,
                     '2 Time':time.ctime(),
                     '3 CV':'{}/{}.'.format(i+1, folds),
                     '5 Model': modelname,
                     '100 Comment': name,
                     '10 Epochs': epochs,
                     '11 Val acc': '{:.2f}'.format(val_acc*100),
                     '12 Val f1': '{:.2f}'.format(val_f1*100),
                     '13 Test acc':'{:.2f}'.format( test_acc*100),
                     '14 Test f1': '{:.2f}'.format(test_f1*100),
                     'Test Conf': str(confmat).replace('\n','')}
        tools.save_results(save_dict=save_dict)
        results.append([val_acc, val_f1, test_acc, test_f1, confmat])
        
        try:
            with open('{}_{}_{}_results.pkl'.format(counter,modelname,name), 'wb') as f:
                pickle.dump(results, f)
        except Exception as e:
            print("Error while saving results: ", e)
        sys.stdout.flush()
        
    return results



class Checkpoint(keras.callbacks.Callback):
    """
    Callback routine for Keras
    Calculates accuracy and f1-score on the validation data
    Implements early stopping if no improvement on validation data for X epochs
    """
    def __init__(self, validation_data, counter = 0, verbose=0, 
                 epochs_to_stop=15, plot = False):
        super(Checkpoint, self).__init__()
        self.val_data = validation_data
        self.best_weights = None
        self.verbose = verbose
        self.counter = counter
        self.plot = plot
        self.epochs_to_stop = epochs_to_stop
        self.figures = []
        

    def on_train_begin(self, logs={}):
        self.loss = []
        self.val_loss = []
        self.acc = []
        self.val_f1 = []
        self.val_acc = []
        
        self.not_improved=0
        self.best_f1 = 0
        self.best_acc = 0
        self.best_epoch = 0
        if self.plot: 
#            plt.close('all')
            self.figures.append(plt.figure())
        
    def on_epoch_end(self, epoch, logs={}):
        y_pred = self.model.predict(self.val_data[0], self.params['batch_size'])
        y_true = self.val_data[1]
        f1 = f1_score(np.argmax(y_pred,1),np.argmax(y_true,1), average="macro")
        acc = accuracy_score(np.argmax(y_pred,1),np.argmax(y_true,1))
#        val_loss = keras.metrics.categorical_crossentropy(y_true, np.argmax(y_pred))
        val_loss = log_loss(y_true, y_pred)
        self.loss.append(logs.get('loss'))
        self.acc.append(logs.get('categorical_accuracy'))
        self.val_loss.append(val_loss)
        self.val_f1.append(f1)
        self.val_acc.append(acc)

        if f1 > self.best_f1:
            self.not_improved = 0
            self.best_f1 = f1
            self.best_acc = acc
            self.best_epoch = epoch
            self.best_weights = self.model.get_weights()
            if self.verbose==1: print('+', end='')
        else:
            self.not_improved += 1
            if self.verbose==1: print('.', end='')
            if self.not_improved > self.epochs_to_stop and self.epochs_to_stop:
                print("\nNo improvement after epoch {}".format(epoch), flush=True)
                self.model.stop_training = True
                
        if self.plot:
            plt.clf()
            plt.subplot(1,2,1)
            plt.title
            plt.plot(self.loss)
            plt.plot(self.val_loss, 'r')
            plt.title('Loss')
            plt.legend(['loss', 'val_loss'])
            plt.xlabel('Epoch')
            plt.ylabel('Loss')
            plt.subplot(1,2,2)
            plt.plot(self.val_acc)
            plt.plot(self.val_f1)
            plt.legend(['val acc', 'val f1'])
            plt.xlabel('Epoch')
            plt.ylabel('%')
            plt.title('Best: acc {:.1f}, f1 {:.1f}'.format(self.best_acc*100,self.best_f1*100))
            plt.show()
            plt.pause(0.0001)
        
        if self.verbose == 2:
            print('Epoch {}: , current: {:.1f}/{:.1f}, best: {:.1f}/{:.1f}'.format(epoch, acc*100, f1*100, self.best_acc*100 , self.best_f1*100))
        
    def on_train_end(self, logs={}):
        self.model.set_weights(self.best_weights)
        sys.stdout.flush()
        try:
            self.model.save(os.path.join('.','weights', str(self.counter) + self.model.name))
        except Exception as error:
            print("Got an error while saving model: {}".format(error))
        return
    


def generator(X, Y, batch_size, random=False, truncate=False, val=False):
    """
        Data generator util for Keras. 
        Generates data in such a way that it can be used with a stateful RNN

    :param X: data (either train or val) with shape 
    :param Y: labels (either train or val) with shape 
    :param num_of_batches: number of batches (a keras thing)
    :param random: randomize pos or neg within a batch

    :return: patches (batch_size, 15, 15, 15) and labels (batch_size,)
    """
    assert len(X)==len(Y), 'X and Y not the same length'
    step = 0
    num_of_batches = len(X)//batch_size
    while True:
        assert len(X)//batch_size==num_of_batches, 'generator error, batch_size and # batches do not match'
        if truncate and step==num_of_batches:
            step = 0
        x_batch = [X[(seq * num_of_batches + step) % len(X)] for seq in range(batch_size)]
        y_batch = [Y[(seq * num_of_batches + step) % len(X)] for seq in range(batch_size)]
        y_weights = np.ones(len(y_batch))
        y_weights[np.argmax(y_batch,1)==1] = 3
        step+=1
        if random:
            shuffle(x_batch, y_batch)
        # yield np.expand_dims(inputs, -1), keras.utils.to_categorical(targets, num_classes=2)
        yield (np.array(x_batch), np.array(y_batch), y_weights) if not val else np.array(x_batch)
        
def plot_history(history):
        plt.subplot(1,2,1)
        plt.plot(history['loss'],'r')
        plt.legend(['Loss'])
        plt.xlabel('epoch')
        plt.subplot(1,2,2)
        plt.plot(history['acc'], 'b')
        plt.plot(history['val_f1'],'m')
        plt.plot(history['val_acc'],'r')
        plt.legend(['Acc','Val f1', 'Val Acc'] )
        plt.xlabel('epoch')
        plt.show()
        plt.pause(0.001)
        
print ('loaded keras_utils.py')
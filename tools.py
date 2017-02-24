# -*- coding: utf-8 -*-
"""
Created on Tue Dec  6 13:33:45 2016

@author: Simon

These are tools for the AutoSleepScorer.
"""

import csv
import numpy as np
import os.path
#import pyfftw
from scipy import fft
from scipy import stats
from sklearn.preprocessing import OneHotEncoder
from sklearn.utils import shuffle
import json
import os
import re

def zscore(*arrays):
    """
        Normalization all arrays with values from the first array.
    """ 
    for array in arrays:
        array[array>-3e+30] = 0
    meanV = np.mean(arrays[0], axis =  0) # vector of mean values
    stdV  = np.std(arrays[0], axis =  0)  # vector of standard deviation values
    for array in arrays:
        array = ((array-meanV)/stdV)
    return arrays

def normalize(signals):
    """
    :param signals: 1D, 2D or 3D signals
    returns each element to have mean 0
    """
    if signals.ndim == 1: signals = np.expand_dims(signals,0) 
    if signals.ndim == 2: signals = np.expand_dims(signals,2)
    new_signals = np.zeros(signals.shape, dtype=np.int32)
    for i in np.arange(signals.shape[2]):
        new_signals[:,:,i] = np.subtract(signals[:,:,i].T,np.mean(signals[:,:,i],axis=1)).T
        
    return new_signals.squeeze() if new_signals.shape[2]==1 else new_signals


def future(signals, fsteps):
    """
    adds fsteps points of the future to the signal
    :param signals: 2D or 3D signals
    :param fsteps: how many future steps should be added to each data point
    """
    if fsteps==0: return signals
    assert signals.shape[0] > fsteps, 'Future steps must be smaller than number of datapoints'
    if signals.ndim == 2: signals = np.expand_dims(signals,2) 
    nsamp = signals.shape[1]
    new_signals = np.zeros((signals.shape[0],signals.shape[1]*(fsteps+1), signals.shape[2]),dtype=np.float32)
    for i in np.arange(fsteps+1):
        new_signals[:,i*nsamp:(i+1)*nsamp,:] = np.roll(signals[:,:,:],-i,axis=0)
    return new_signals.squeeze() if new_signals.shape[2]==1 else new_signals


def feat_eeg(signals):
    """
    calculate the relative power as defined by Leangkvist (2012),
    assuming signal is recorded with 100hz
    """
    if signals.ndim == 1: signals = np.expand_dims(signals,0)
    
    sfreq = 100.0
    nsamp = float(signals.shape[1])
    feats = np.zeros((signals.shape[0],8),dtype='float32')
    # 5 FEATURE for freq babnds
    w = (fft(signals,axis=1)).real
    delta = np.sum(np.abs(w[:,np.arange(0.5*nsamp/sfreq,4*nsamp/sfreq, dtype=int)]),axis=1)
    theta = np.sum(np.abs(w[:,np.arange(4*nsamp/sfreq,8*nsamp/sfreq, dtype=int)]),axis=1)
    alpha = np.sum(np.abs(w[:,np.arange(8*nsamp/sfreq,13*nsamp/sfreq, dtype=int)]),axis=1)
    beta  = np.sum(np.abs(w[:,np.arange(13*nsamp/sfreq,20*nsamp/sfreq, dtype=int)]),axis=1)
    gamma = np.sum(np.abs(w[:,np.arange(20*nsamp/sfreq,50*nsamp/sfreq, dtype=int)]),axis=1)   # only until 50, because hz=100
    sum_abs_pow = delta + theta + alpha + beta + gamma
    feats[:,0] = delta /sum_abs_pow
    feats[:,1] = theta /sum_abs_pow
    feats[:,2] = alpha /sum_abs_pow
    feats[:,3] = beta  /sum_abs_pow
    feats[:,4] = gamma /sum_abs_pow
    feats[:,5] = np.log10(stats.kurtosis(signals,fisher=False,axis=1))        # kurtosis
    feats[:,6] = np.log10(-np.sum([(x/nsamp)*(np.log(x/nsamp)) for x in np.apply_along_axis(lambda x: np.histogram(x, bins=8)[0], 1, signals)],axis=1))  # entropy.. yay, one line...
    #feats[:,7] = np.polynomial.polynomial.polyfit(np.log(f[np.arange(0.5*nsamp/sfreq,50*nsamp/sfreq, dtype=int)]), np.log(w[0,np.arange(0.5*nsamp/sfreq,50*nsamp/sfreq, dtype=int)]),1)
    feats[:,7] = np.dot(np.array([3.5,4,5,7,30]),feats[:,0:5].T ) / (sfreq/2-0.5)
    return np.nan_to_num(feats)


def feat_eog(signals):
    """
    calculate the EOG features
    :param signals: 1D or 2D signals
    """

    if signals.ndim == 1: signals = np.expand_dims(signals,0)
    sfreq = 100.0
    nsamp = float(signals.shape[1])
    w = (fft(signals,axis=1)).real   
    feats = np.zeros((signals.shape[0],15),dtype='float32')
    delta = np.sum(np.abs(w[:,np.arange(0.5*nsamp/sfreq,4*nsamp/sfreq, dtype=int)]),axis=1)
    theta = np.sum(np.abs(w[:,np.arange(4*nsamp/sfreq,8*nsamp/sfreq, dtype=int)]),axis=1)
    alpha = np.sum(np.abs(w[:,np.arange(8*nsamp/sfreq,13*nsamp/sfreq, dtype=int)]),axis=1)
    beta  = np.sum(np.abs(w[:,np.arange(13*nsamp/sfreq,20*nsamp/sfreq, dtype=int)]),axis=1)
    gamma = np.sum(np.abs(w[:,np.arange(20*nsamp/sfreq,50*nsamp/sfreq, dtype=int)]),axis=1)   # only until 50, because hz=100
    sum_abs_pow = delta + theta + alpha + beta + gamma
    feats[:,0] = delta /sum_abs_pow
    feats[:,1] = theta /sum_abs_pow
    feats[:,2] = alpha /sum_abs_pow
    feats[:,3] = beta  /sum_abs_pow
    feats[:,4] = gamma /sum_abs_pow
    feats[:,5] = np.dot(np.array([3.5,4,5,7,30]),feats[:,0:5].T ) / (sfreq/2-0.5) #smean
    feats[:,6] = np.max(signals, axis=1)    #PAV
    feats[:,7] = np.min(signals, axis=1)    #VAV   
    feats[:,8] = np.argmax(signals, axis=1) #PAP
    feats[:,9] = np.argmin(signals, axis=1) #VAP
    feats[:,10] = np.sum(np.abs(signals), axis=1)/ np.mean(np.sum(np.abs(signals), axis=1)) # AUC
    feats[:,11] = np.sum(((np.roll(np.sign(signals), 1,axis=1) - np.sign(signals)) != 0).astype(int),axis=1) #TVC
    feats[:,12] = np.log10(np.std(signals, axis=1)) #STD/VAR
    feats[:,13] = np.log10(stats.kurtosis(signals,fisher=False,axis=1))       # kurtosis
    feats[:,14] = np.log10(-np.sum([(x/nsamp)*(np.log(x/nsamp)) for x in np.apply_along_axis(lambda x: np.histogram(x, bins=8)[0], 1, signals)],axis=1))  # entropy.. yay, one line...
    
    return np.nan_to_num(feats)


def feat_emg(signals):
    """
    calculate the EMG median as defined by Leangkvist (2012),
    """
    if signals.ndim == 1: signals = np.expand_dims(signals,0)
    sfreq = 100.0
    nsamp = float(signals.shape[1])
    w = (fft(signals,axis=1)).real   
    feats = np.zeros((signals.shape[0],13),dtype='float32')
    delta = np.sum(np.abs(w[:,np.arange(0.5*nsamp/sfreq,4*nsamp/sfreq, dtype=int)]),axis=1)
    theta = np.sum(np.abs(w[:,np.arange(4*nsamp/sfreq,8*nsamp/sfreq, dtype=int)]),axis=1)
    alpha = np.sum(np.abs(w[:,np.arange(8*nsamp/sfreq,13*nsamp/sfreq, dtype=int)]),axis=1)
    beta  = np.sum(np.abs(w[:,np.arange(13*nsamp/sfreq,20*nsamp/sfreq, dtype=int)]),axis=1)
    gamma = np.sum(np.abs(w[:,np.arange(20*nsamp/sfreq,50*nsamp/sfreq, dtype=int)]),axis=1)   # only until 50, because hz=100
    sum_abs_pow = delta + theta + alpha + beta + gamma
    feats[:,0] = delta /sum_abs_pow
    feats[:,1] = theta /sum_abs_pow
    feats[:,2] = alpha /sum_abs_pow
    feats[:,3] = beta  /sum_abs_pow
    feats[:,4] = gamma /sum_abs_pow
    feats[:,5] = np.dot(np.array([3.5,4,5,7,30]),feats[:,0:5].T ) / (sfreq/2-0.5) #smean
    emg = np.sum(np.abs(w[:,np.arange(12.5*nsamp/sfreq,32*nsamp/sfreq, dtype=int)]),axis=1)
    feats[:,6] = emg / np.sum(np.abs(w[:,np.arange(8*nsamp/sfreq,32*nsamp/sfreq, dtype=int)]),axis=1)  # ratio of high freq to total motor
    feats[:,7] = np.median(np.abs(w[:,np.arange(8*nsamp/sfreq,32*nsamp/sfreq, dtype=int)]),axis=1)    # median freq
    feats[:,8] = np.mean(np.abs(w[:,np.arange(8*nsamp/sfreq,32*nsamp/sfreq, dtype=int)]),axis=1)    #  mean freq
    feats[:,9] = np.std(signals, axis=1)    #  std 
    feats[:,10] = np.mean(signals,axis=1)
    feats[:,11] = np.log10(stats.kurtosis(signals,fisher=False,axis=1) )
    feats[:,12] = np.log10(-np.sum([(x/nsamp)*(np.log(x/nsamp)) for x in np.apply_along_axis(lambda x: np.histogram(x, bins=8)[0], 1, signals)],axis=1))  # entropy.. yay, one line...
    return np.nan_to_num(feats)


def feat_emgmedianfreq(signals):
    """
    calculate the EMG median as defined by Leangkvist (2012),
    """
    if signals.ndim == 1: signals = np.expand_dims(signals,0)
    return np.median(abs(signals),axis=1)


def get_features(data):
    """
    returns a vector with extraced features
    :param data: datapoints x samples x dimensions (dimensions: EEG,EOG,EMG)
    """
#    assert(ndims=3)
    for i in np.arange(data.shape[2]):
        
        pass
    

def natural_key(string_):
    """See http://www.codinghorror.com/blog/archives/001018.html"""
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]      
        
def jsondict2csv(json_file, csv_file):
    
    key_set = set()
    dict_list = list()
    try:
        with open(json_file) as f:
            for line in f:
                dic = json.loads(line)
                map(key_set.add,dic.keys())
                dict_list.append(dic)
        keys = list(sorted(key_set, key = natural_key))
    
        with open(csv_file, 'wb') as f:
            w = csv.DictWriter(f, keys, delimiter=';')
            w.writeheader()
            w.writerows(dict_list)
    except IOError:
        print('could not convert to csv-file. ')
    
def append_json(json_filename, dic):
    with open(json_filename, 'a') as f:
        json.dump(dic, f)
        f.write('\n')    

def memory():
    from wmi import WMI
    w = WMI('.')
    result = w.query("SELECT WorkingSet FROM Win32_PerfRawData_PerfProc_Process WHERE IDProcess=%d" % os.getpid())
    return int(result[0].WorkingSet)/1024**2
    


def one_hot(hypno, n_categories):
    enc = OneHotEncoder(n_values=n_categories)
    hypno = enc.fit_transform(hypno).toarray()
    return np.array(hypno,'int32')
    
    
def shuffle_lists(*args,**options):
     """ function which shuffles two lists and keeps their elements aligned
         for now use sklearn, maybe later get rid of dependency
     """
     return shuffle(*args,**options)
    
    
def epoch_voting(Y, chunk_size):
    
    
    Y_new = Y.copy()
    
    for i in range(1+len(Y_new)/chunk_size):
        epoch = Y_new[i*chunk_size:(i+1)*chunk_size]
        if len(epoch) != 0: winner = np.bincount(epoch).argmax()
        Y_new[i*chunk_size:(i+1)*chunk_size] = winner              
    return Y_new

        

    
    
def get_freq_bands (epoch): # DEPRECATED
    print('get_freq_bands is deprecated, use get_freqs')
    w = (fft(epoch,axis=0)).real
    w = w[:len(w)/2]
    w = np.split(w,50)
    for i in np.arange(50):
        w[i] = np.mean(w[i],axis=0)
    
    return np.array(np.abs(w))



def get_freqs (signals, nbins=0):
    """ extracts relative fft frequencies and bins them in n bins
    :param signals: 1D or 2D signals
    :param nbins:  number of bins used as output (default: maximum possible)
    """
    if signals.ndim == 1: signals = np.expand_dims(signals,0)
    sfreq = 100.0
    if nbins == 0: nbins = int(sfreq/2)
    
    nsamp = float(signals.shape[1])
    assert nsamp/2 >= nbins, 'more bins than fft results' 
    
    feats = np.zeros((int(signals.shape[0]),nbins),dtype='float32')
    w = (fft(signals,axis=1)).real
    for i in np.arange(nbins):
        feats[:,i] =  np.sum(np.abs(w[:,np.arange(i*nsamp/sfreq,(i+1)*nsamp/sfreq, dtype=int)]),axis=1)
    sum_abs_pow = np.sum(feats,axis=1)
    feats = (feats.T / sum_abs_pow).T
    return feats
       

print ('loaded tools.py')
    

    
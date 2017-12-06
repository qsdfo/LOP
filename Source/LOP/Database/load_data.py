#!/usr/bin/env python
# -*- coding: utf8 -*-

# A basic checksum mechanism has been implemented to guarantee that we maintain the same train/test/valid between the moment we
# loaded the files for training and the post-processing steps (generations)

import numpy as np
import logging
import random
import cPickle as pickle


def load_data(data_folder, set_identifier, temporal_order=20, batch_size=100,
              skip_sample=1, avoid_silence=True, binarize_piano=False, binarize_orchestra=True, logger_load=None, generation_length=100):

    # If no logger, create one
    if logger_load is None:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                            datefmt='%m-%d %H:%M',
                            filename='load.log',
                            filemode='w')
        logger_load = logging.getLogger('load')

    piano = np.load(data_folder + '/piano_' + set_identifier + '.npy')
    orchestra = np.load(data_folder + '/orchestra_' + set_identifier + '.npy')

    # Binarize inputs ?
    if binarize_piano:
        piano[np.nonzero(piano)] = 1
    else:
        piano = piano / 127
    if binarize_orchestra:
        orchestra[np.nonzero(orchestra)] = 1
    else:
        orchestra = orchestra / 127

    # Get start and end for each track
    tracks_start_end = pickle.load(open(data_folder + '/tracks_start_end_' + set_identifier + '.pkl', 'rb'))

    # Get valid indices given start_track, end_track and temporal_order
    # Consider that you might use both past and future indformation, 
    # i.e.interval [t - temporal_order ; t + temporal_order]
    def valid_indices(tracks_start_end, temporal_order):
        valid_ind = []
        for (start_track, end_track) in tracks_start_end.values():
            valid_ind.extend(range(start_track+temporal_order-1, end_track-temporal_order+1, skip_sample))
        return valid_ind

    def remove_silences(indices, pr):
        flat_pr = pr.sum(axis=1)
        return [e for e in indices if (flat_pr[e] != 0)]


    def last_indices(tracks_start_end, temporal_order):
        valid_ind = []
        for (start_track, end_track) in tracks_start_end.values():
            # If the middle of the track is more than temporal_order,
            # Then store it as a generation index
            # if not, take the last index
            # If last index is still not enough, just skip the track
            half_duration = (end_track-start_track) / 2
            middle_track = start_track + half_duration
            if half_duration > temporal_order:
                valid_ind.append(middle_track)
            elif (end_track-start_track) > temporal_order:
                valid_ind.append(end_track-1)
        return valid_ind

    def build_batches(valid_ind):
        batches = []
        position = 0
        n_batch = int(len(valid_ind) // batch_size)

        # Shuffle indices
        random.shuffle(valid_ind)

        for i in range(n_batch):
            batches.append(valid_ind[position:position+batch_size])
            position += batch_size
        return batches

    indices = valid_indices(tracks_start_end, temporal_order)
    
    if avoid_silence:
        # Remove both... a bit brute force
        indices = remove_silences(indices, orchestra)
        indices = remove_silences(indices, piano)
    batches = build_batches(indices)

    # Generation indices :
    #       For each track :
    #           - middle of track is > temporal_order
    #           - end if not
    #           - nothing if end < temporal_order
    if set_identifier == 'test':
        generation_index = last_indices(tracks_start_end, generation_length)

    if set_identifier == 'test':
        return piano, orchestra, np.asarray(batches, dtype=np.int32), np.asarray(generation_index, dtype=np.int32)
    else:
        return piano, orchestra, np.asarray(batches, dtype=np.int32)


# Wrappers
def load_data_train(data_folder, temporal_order=20, batch_size=100, skip_sample=1, avoid_silence=True, binarize_piano=False, binarize_orchestra=True, logger_load=None, generation_length=100):
    return load_data(data_folder, 'train', temporal_order=temporal_order, batch_size=batch_size,
                     skip_sample=skip_sample, avoid_silence=avoid_silence, binarize_piano=binarize_piano, binarize_orchestra=binarize_orchestra, logger_load=logger_load, generation_length=generation_length)


def load_data_valid(data_folder, temporal_order=20, batch_size=100, skip_sample=1, avoid_silence=False, binarize_piano=False, binarize_orchestra=True, logger_load=None, generation_length=100):
    return load_data(data_folder, 'valid', temporal_order=temporal_order, batch_size=batch_size,
                     skip_sample=skip_sample, avoid_silence=avoid_silence, binarize_piano=binarize_piano, binarize_orchestra=binarize_orchestra, logger_load=logger_load, generation_length=generation_length)


def load_data_test(data_folder, temporal_order=20, batch_size=100, skip_sample=1, avoid_silence=False, binarize_piano=False, binarize_orchestra=True, logger_load=None, generation_length=100):
    return load_data(data_folder, 'test', temporal_order=temporal_order, batch_size=batch_size,
                     skip_sample=skip_sample, avoid_silence=avoid_silence, binarize_piano=binarize_piano, binarize_orchestra=binarize_orchestra, logger_load=logger_load, generation_length=generation_length)

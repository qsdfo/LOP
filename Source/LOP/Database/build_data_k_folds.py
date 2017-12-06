#!/usr/bin/env python
# -*- coding: utf-8-unix -*-


#################################################
#################################################
#################################################
# Note :
#   - pitch range for each instrument is set based on the observed pitch range of the database
#   - for test set, we picked seminal examples. See the name_db_{test;train;valid}.txt files that
#       list the files path :
#           - beethoven/liszt symph 5 - 1 : liszt_classical_archive/16
#           - mouss/ravel pictures exhib : bouliane/22
#################################################
#################################################
#################################################


import os
import numpy as np
import LOP.Scripts.config as config

from LOP_database.utils.build_dico import build_dico
import build_data_aux
import cPickle as pickle


# Avoid paths
avoid_paths = [
    "imslp/75",
    "imslp/82",
    "imslp/83",
    "hand_picked_Spotify/6",  # Concerto
    "hand_picked_Spotify/18",
    "hand_picked_Spotify/19",
    "hand_picked_Spotify/2",
    "hand_picked_Spotify/36",
    "hand_picked_Spotify/43",
    "hand_picked_Spotify/46",
    "hand_picked_Spotify/50",
    "hand_picked_Spotify/60",
    "hand_picked_Spotify/61"
]


def get_dim_matrix(root_dir, folder_paths, meta_info_path='temp.p', quantization=12, temporal_granularity='frame_level', logging=None):
    logging.info("##########")
    logging.info("Get dimension informations")
    # Determine the temporal size of the matrices
    # If the two files have different sizes, we use the shortest (to limit the use of memory,
    # we better contract files instead of expanding them).
    # Get instrument names
    instrument_list_from_dico = build_dico().keys()
    instru_mapping = {}
    # instru_mapping = {'piano': {'pitch_min': 24, 'pitch_max':117, 'ind_min': 0, 'ind_max': 92},
    #                         'harp' ... }
    T = 0
    for folder_path_relative in folder_paths:
        folder_path = root_dir + '/' + folder_path_relative.rstrip()
        logging.info(folder_path)
        if not os.path.isdir(folder_path):
            continue

        # Read pr
        pr_piano, _, _, instru_piano, _, pr_orch, _, _, instru_orch, _, duration =\
            build_data_aux.process_folder(folder_path, quantization, temporal_granularity, gapopen=3, gapextend=1)

        if duration is None:
            # Files that could not be aligned
            continue
        T += duration

        # Modify the mapping from instrument to indices in pianorolls and pitch bounds
        instru_mapping = build_data_aux.instru_pitch_range(instrumentation=instru_piano,
                                                           pr=pr_piano,
                                                           instru_mapping=instru_mapping,
                                                           instrument_list_from_dico=instrument_list_from_dico,
                                                           )
        # remark : instru_mapping would be modified if it is only passed to the function,
        #                   f(a)  where a is modified inside the function
        # but i prefer to make the reallocation explicit
        #                   a = f(a) with f returning the modified value of a.
        # Does it change anything for computation speed ? (Python pass by reference,
        # but a slightly different version of it, not clear to me)
        instru_mapping = build_data_aux.instru_pitch_range(instrumentation=instru_orch,
                                                           pr=pr_orch,
                                                           instru_mapping=instru_mapping,
                                                           instrument_list_from_dico=instrument_list_from_dico
                                                           )
    # Build the index_min and index_max in the instru_mapping dictionary
    counter = 0
    for k, v in instru_mapping.iteritems():
        if k == 'Piano':
            index_min = 0
            index_max = v['pitch_max'] - v['pitch_min']
            v['index_min'] = index_min
            v['index_max'] = index_max
            continue
        index_min = counter
        counter = counter + v['pitch_max'] - v['pitch_min']
        index_max = counter
        v['index_min'] = index_min
        v['index_max'] = index_max

    # Instanciate the matrices
    ########################################
    ########################################
    ########################################
    temp = {}
    temp['instru_mapping'] = instru_mapping
    temp['quantization'] = quantization
    temp['T'] = T
    temp['N_orchestra'] = counter
    pickle.dump(temp, open(meta_info_path, 'wb'))
    return


def cast_pr(new_pr_orchestra, new_instru_orchestra, new_pr_piano, start_time, duration, instru_mapping, pr_orchestra, pr_piano, logging=None):
    pr_orchestra = build_data_aux.cast_small_pr_into_big_pr(new_pr_orchestra, new_instru_orchestra, start_time, duration, instru_mapping, pr_orchestra)
    pr_piano = build_data_aux.cast_small_pr_into_big_pr(new_pr_piano, {}, start_time, duration, instru_mapping, pr_piano)


def build_data(root_dir, folder_paths, meta_info_path='temp.p', quantization=12, temporal_granularity='frame_level', store_folder='../Data', pitch_translation_augmentations=[0], logging=None):

    # Get dimensions
    get_dim_matrix(root_dir, folder_paths, meta_info_path=meta_info_path, quantization=quantization, temporal_granularity=temporal_granularity, logging=logging)
    
    logging.info("##########")
    logging.info("Build data")

    statistics = {}

    temp = pickle.load(open(meta_info_path, 'rb'))
    instru_mapping = temp['instru_mapping']
    quantization = temp['quantization']
    T = temp['T']
    N_orchestra = temp['N_orchestra']
    N_piano = instru_mapping['Piano']['index_max']

    pr_orchestra = np.zeros((T, N_orchestra), dtype=np.float32)
    pr_piano = np.zeros((T, N_piano), dtype=np.float32)
    duration_piano = np.zeros((T), dtype=np.int)
    duration_orch = np.zeros((T), dtype=np.int)

    # Write the prs in the matrix
    time = 0
    tracks_start_end = {}

    for folder_path_relative in folder_paths:
        folder_path = root_dir + '/' + folder_path_relative.rstrip()
        logging.info(folder_path)
        if not os.path.isdir(folder_path):
            continue

        # Get pr, warped and duration
        new_pr_piano, _, new_duration_piano, _, _, new_pr_orchestra, _, new_duration_orch, new_instru_orchestra, _, duration\
            = build_data_aux.process_folder(folder_path, quantization, temporal_granularity, gapopen=3, gapextend=1)

        # SKip shitty files
        if new_pr_piano is None:
            # It's definitely not a match...
            # Check for the files : are they really a piano score and its orchestration ??
            with(open('log_build_db.txt', 'a')) as f:
                f.write(folder_path + '\n')
            continue

        # and cast them in the appropriate bigger structure
        cast_pr(new_pr_orchestra, new_instru_orchestra, new_pr_piano, time,
                duration, instru_mapping, pr_orchestra, pr_piano, logging)

        duration_piano[time:time+duration] = new_duration_piano
        duration_orch[time:time+duration] = new_duration_orch

        # Store beginning and end of this track
        tracks_start_end[folder_path] = (time, time+duration)

        # Increment time counter
        time += duration

        # Compute statistics
        for track_name, instrument_name in new_instru_orchestra.iteritems():
            # Number of note played by this instru
            if track_name not in new_pr_orchestra.keys():
                continue
            n_note_played = (new_pr_orchestra[track_name] > 0).sum()
            if instrument_name in statistics:
                # Track appearance
                statistics[instrument_name]['n_track_present'] = statistics[instrument_name]['n_track_present'] + 1
                statistics[instrument_name]['n_note_played'] = statistics[instrument_name]['n_note_played'] + n_note_played
            else:
                statistics[instrument_name] = {}
                statistics[instrument_name]['n_track_present'] = 1
                statistics[instrument_name]['n_note_played'] = n_note_played

    with open(store_folder + '/orchestra.npy', 'wb') as outfile:
        np.save(outfile, pr_orchestra)
    with open(store_folder + '/piano.npy', 'wb') as outfile:
        np.save(outfile, pr_piano)
    with open(store_folder + '/duration_orchestra.npy', 'wb') as outfile:
        np.save(outfile, duration_orch)
    with open(store_folder + '/duration_piano.npy', 'wb') as outfile:
        np.save(outfile, duration_piano)
    pickle.dump(tracks_start_end, open(store_folder + '/tracks_start_end.pkl', 'wb'))

    # Save pr_orchestra, pr_piano, instru_mapping
    metadata = {}
    metadata['quantization'] = quantization
    metadata['N_orchestra'] = N_orchestra
    metadata['N_piano'] = N_piano
    metadata['instru_mapping'] = instru_mapping
    metadata['quantization'] = quantization
    metadata['temporal_granularity'] = temporal_granularity
    metadata['store_folder'] = store_folder

    with open(store_folder + '/metadata.pkl', 'wb') as outfile:
        pickle.dump(metadata, outfile)

    # Write statistics in a csv
    header = "instrument_name;n_track_present;n_note_played"
    with open(store_folder + '/statistics.csv', 'wb') as csvfile:
        csvfile.write(header+'\n')
        for instru_name, dico_stat in statistics.iteritems():
            csvfile.write(instru_name + u';' +
                          str(statistics[instru_name]['n_track_present']) + u';' +
                          str(statistics[instru_name]['n_note_played']) + '\n')


if __name__ == '__main__':
    import logging
    # log file
    log_file_path = 'log_build_data'
    # set up logging to file - see previous section for more details
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M',
                        filename=log_file_path,
                        filemode='w')
    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

    # Set up
    # NOTE : can't do data augmentation with K-folds, or it would require to build K times the database
    # because train is data augmented but not test and validate
    temporal_granularity = 'event_level'
    quantization = 8

    DATABASE_PATH = config.database_root() + '/LOP_database_06_09_17'
    DATABASE_NAMES = ["bouliane", "hand_picked_Spotify", "liszt_classical_archives", "imslp"]
#    DATABASE_NAMES = ["debug"]

    data_folder = '../../../Data_folds/Data'
    data_folder += '__' + temporal_granularity + str(quantization)

    if not os.path.isdir(data_folder):
        os.makedirs(data_folder)

    # Create a list of paths
    folder_paths = []
    for db_name in DATABASE_NAMES:
        path = DATABASE_PATH + '/' + db_name

        for file_name in os.listdir(path):
            if file_name != '.DS_Store':
                this_path = db_name + '/' + file_name
                if this_path not in avoid_paths:
                    folder_paths.append(this_path)

    build_data(root_dir=DATABASE_PATH,
               folder_paths=folder_paths,
               meta_info_path=data_folder + '/temp.p',
               quantization=quantization,
               temporal_granularity=temporal_granularity,
               store_folder=data_folder,
               logging=logging)

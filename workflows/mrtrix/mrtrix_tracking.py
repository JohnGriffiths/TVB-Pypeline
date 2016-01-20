
# coding: utf-8

# # Pipeline MRTrix 0.2 tractography workflow

# This workflow has to be connected straight subsequentially to the <b>MRTrix 0.2 preprocessing workflow</b>.
# Continuing on the files generated by it's predecessor, this workflow will perform the actual fiber tracking for a <b>single seed mask</b>. Thus it will generate a single tractograpy file and it intended to be run in parallel by a surounding scaffold workflow.

# In[2]:

# import nipype.interfaces.mrtrix as mrt
from nipype import Node, Workflow, MapNode, Function
from nipype.interfaces.utility import IdentityInterface

import logging


# ### Start the logging

logger = logging.getLogger('interface')
logger.setLevel(logging.INFO)
# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# add formatter to ch
ch.setFormatter(formatter)
# add ch to logger
logger.addHandler(ch)


# ### Define Input- and Output-Node

inputNode = Node(IdentityInterface(fields = ['wmmask_1mm',
                                            'spherical_harmonics_image',
                                            'seedmask',
                                            'targetmask',
                                            'seed_count',
                                            'delete_tmp_files',
                                            'tracks_dir']), 
                    name = 'input_node')


outputNode = Node(IdentityInterface(fields = ['trk_file']), 
                  name = 'output_node')


# ### Utility functions

def fileNameBuild(path, seedmasks):
    import re
    from os.path import basename
    #res = re.search("\d{4,999}", seedmask)
    #seedMskIdx = res.group()
    res = [re.search("(\d{4,999})_.*$", basename(x)).group(1) for x in seedmasks]
    return [path + '/' + seedMskIdx + '_tracks.tck' for seedMskIdx in res]

fileNameNode = Node(Function(input_names = ['path', 'seedmasks'],
                             output_names = ['seedmaskFilenames'],
                             function = fileNameBuild),
                    name = 'tckFilenameBuilder')


def fiberTracking(out_file_tck, in_file, seed_file, include_file, mask_file, desired_number_of_tracks,
                  inputmodel = None, min_tract_length = None, stop = None, step_size = None,
                  unidrectional = None, no_mask_interpolation = None, delete_tmp_files = None):
    import nipype.interfaces.mrtrix as mrt
    import os, logging
    from numpy import save

    # Calling Kenny Loggins
    dangerZone = logging.getLogger('interface')
    dangerZone.setLevel('WARNING')

    if inputmodel is None:
        inputmodel = 'SD_PROB'
    if min_tract_length is None:
        min_tract_length = 30
    if stop is None:
        stop = True
    if step_size is None:
        step_size = 0.2
    if unidrectional is None:
        unidrectional = True
    if no_mask_interpolation is None:
        no_mask_interpolation = True

    tracker = mrt.StreamlineTrack()
    tracker.inputs.inputmodel = inputmodel
    tracker.inputs.minimum_tract_length = min_tract_length
    tracker.inputs.stop = stop
    tracker.inputs.no_mask_interpolation = no_mask_interpolation
    tracker.inputs.step_size = step_size
    tracker.inputs.unidirectional = unidrectional

    tracker.inputs.in_file = in_file
    tracker.inputs.seed_file = seed_file
    tracker.inputs.out_file = out_file_tck
    tracker.inputs.include_file = include_file
    tracker.inputs.mask_file = mask_file
    tracker.inputs.desired_number_of_tracks = desired_number_of_tracks
    # Perform the fiber tracking
    tracker.run()

    # ### Convert tck to trk
    # Now we convert the resulting tck file from the hard drive into a Trackvis trk file
    # By default, the tck is then deleted to save storage space. This parameter can be overwritten
    # The reason for this is simply that we want to obtain files having the sama data schema independent from
    # the particullar toolbox choosen for tracktography
    #
    # out_file_trk = out_file_tck[:-3] + 'trk'
    #
    # tck2trk = mrt.convert.MRTrix2TrackVis()
    # tck2trk.inputs.in_file = out_file_tck
    # tck2trk.inputs.image_file = seed_file
    # tck2trk.inputs.out_filename = out_file_trk
    # tck2trk.run()


    # Convert to numpy format
    # The convention for the pipeline is that the tracks in each file are stored as a list containing Nx3 arrays
    # of track coords in RAS-mm space (default behaviour of MRTrix)
    # This list is embedded into a dict of the header holding valuable information about the track-file
    tracks_header, tracks = mrt.convert.read_mrtrix_tracks(out_file_tck, as_generator=False)
    tracks_header['tracks'] = tracks
    out_file_npy = out_file_tck[:-3] + 'npy'
    save(out_file_npy, tracks_header)

    # Delete tmp files if needed (default is yes)
    if delete_tmp_files is None:
        os.remove(out_file_tck)

    # Releasing Mr Loggins...
    dangerZone.setLevel('NOTSET')

    return out_file_npy

trackingNode = MapNode(Function(input_names=['out_file_tck', 'in_file', 'seed_file', 'include_file', 'mask_file',
                                             'desired_number_of_tracks', 'inputmodel', 'min_tract_length', 'stop',
                                             'step_size', 'unidrectional', 'no_mask_interpolation', 'delete_tmp_files'],
                                output_names=['out_file_trk'],
                                function=fiberTracking),
                       name = 'tracking_node',
                       iterfield = ['seed_file', 'include_file', 'desired_number_of_tracks', 'out_file_tck'])


# #### Debug Stuff
'''
def debugTracking(out_file_tck, in_file, seed_file, include_file, mask_file, desired_number_of_tracks,
                  inputmodel = None, min_tract_length = None, stop = None, step_size = None,
                  unidrectional = None, no_mask_interpolation = None, delete_tmp_files = None):
    out_file_trk = out_file_tck[:-3] + 'trk'
    return out_file_trk

trackingNode = MapNode(Function(input_names=['out_file_tck', 'in_file', 'seed_file', 'include_file', 'mask_file',
                                             'desired_number_of_tracks', 'inputmodel', 'min_tract_length', 'stop',
                                             'step_size', 'unidrectional', 'no_mask_interpolation', 'delete_tmp_files'],
                                output_names=['out_file_trk'],
                                function=debugTracking),
                       name = 'tracking_node',
                       iterfield = ['seed_file', 'include_file', 'desired_number_of_tracks', 'out_file_tck'])
'''
# ### Define the workflow

wf = Workflow('MRTRIX_tracking')

wf.connect([
        (inputNode, fileNameNode, [('tracks_dir', 'path'),
                                   ('seedmask', 'seedmasks')]),
        (fileNameNode, trackingNode, [('seedmaskFilenames', 'out_file_tck')]),
        (inputNode, trackingNode, [('spherical_harmonics_image', 'in_file'),
                                  ('seedmask', 'seed_file'),
                                  ('targetmask', 'include_file'),
                                  ('wmmask_1mm', 'mask_file'),
                                  ('seed_count', 'desired_number_of_tracks')]),
        (trackingNode, outputNode, [('out_file_trk', 'trk_file')])
    ])





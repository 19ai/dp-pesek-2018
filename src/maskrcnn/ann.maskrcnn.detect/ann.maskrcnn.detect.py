#!/usr/bin/env python
#
############################################################################
#
# MODULE:	    ann.maskrcnn.train
# AUTHOR(S):	Ondrej Pesek <pesej.ondrek@gmail.com>
# PURPOSE:	    Train your Mask R-CNN network
# COPYRIGHT:	(C) 2017 Ondrej Pesek and the GRASS Development Team
#
#		This program is free software under the GNU General
#		Public License (>=v2). Read the file COPYING that
#		comes with GRASS for details.
#
#############################################################################

#%module
#% description: Train your Mask R-CNN network
#% keyword: ann
#% keyword: vector
#% keyword: raster
#%end
#%option G_OPT_M_DIR
#% key: images_directory
#% label: Path to a directory with images to detect
#% required: yes
#%end
#%option
#% key: images_format
#% type: string
#% label: Format suffix of images
#% description: .jpg, .tiff, .png, etc.
#% required: yes
#%end
#%option
#% key: model
#% type: string
#% label: Path to the .h5 file containing the model
#% required: yes
#% multiple: no
#%end
#%option
#% key: classes
#% type: string
#% label: Names of classes separated with ","
#% required: yes
#% multiple: yes
#%end
#%option G_OPT_M_DIR
#% key: masks_output
#% label: Directory where masks will be saved
#% description: keep empty to use just temporary files
#% required: no
#%end
#%option
#% key: output_type
#% type: string
#% label: Type of output (TODO: point output)
#% options: area, point
#% answer: area
#% required: no
#%end


import grass.script as gscript
from grass.pygrass.utils import get_lib_path
import os
from subprocess import call
from shutil import copyfile
from random import randint

path = get_lib_path(modname='maskrcnn', libname='py3detect')
if path is None:
    grass.script.fatal('Not able to find the maskrcnn library directory.')

###########################################################
# unfortunately, it needs python3, see file py3train.py
###########################################################


def main(options, flags):

    imagesDir = options['images_directory']
    modelPath = options['model']
    classes = options['classes']
    outputType = options['output_type']
    if options['images_format'][0] != '.':
        format = '.{}'.format(options['images_format'])
    else:
        format = options['images_format']
    masksDir = options['masks_output']
    # TODO: Add checkbox to decide whether keep raster masks or not
    if masksDir == '':
        masksDir = gscript.core.tempfile().rsplit(os.sep, 1)[0]

    # TODO: (3 different brands in case of lot of classes?)
    if len(classes.split(',')) > 255:
        raise SystemExit('Too many classes. Must be less than 256.')
    classesColours = [0] + [i + 1 for i in range(len(classes.split(',')))]

    if len(set(classes.split(','))) != len(classes.split(',')):
        raise SystemExit('ERROR: Two or more classes have the same name.')

    ###########################################################
    # unfortunately, redirect everything to python3
    ###########################################################
    call('python3 {}{}py3detect.py --images_dir={} --model={} --classes={} '
         '--masks_dir={} --output_type={} --colours={} '
         '--format={}'.format(
            path, os.sep,
            imagesDir,
            modelPath,
            classes,
            masksDir,
            outputType,
            ','.join([str(col) for col in classesColours]),
            format),
         shell=True)

    # raise SystemExit(0)
    print('Masks detected. Georeferencing masks...')
    masks = list()
    detectedClasses = list()
    for referencing in [file for file in next(
            os.walk(imagesDir))[2] if (
                os.path.splitext(file)[1] != format and format in file)]:
        fileName, refExtension = referencing.split(format)
        # TODO: Join with converting to one loop
        for i in range(1, len(classes.split(',')) + 1):
            maskName = fileName + '_' + str(i)
            maskFileName = maskName + '.png'
            if os.path.isfile(os.path.join(masksDir, maskFileName)):
                if i not in detectedClasses:
                    detectedClasses.append(i)
                masks.append(maskName)
                copy_georeferencing(imagesDir, masksDir, maskFileName,
                                    refExtension, referencing)

                gscript.run_command('r.in.gdal',
                                    input=os.path.join(masksDir, maskFileName),
                                    output=maskName,
                                    band=1,  # TODO: 3 if 3 band masks
                                    overwrite=gscript.overwrite())

    print('Converting masks to vectors...')
    masksString = ','.join(masks)
    for i in detectedClasses:
        for maskName in masks:
            gscript.run_command('g.region',
                                raster=maskName)
            gscript.run_command('r.mask',
                                raster=maskName,
                                maskcats=classesColours[i])
            gscript.run_command('r.to.vect',
                                's',
                                input=maskName,
                                output=maskName,
                                type=outputType)
            gscript.run_command('r.mask',
                                'r')

        gscript.run_command('v.patch',
                            input=masksString,
                            output=classes.split(',')[i - 1])
        gscript.run_command('g.remove',
                            'f',
                            name=masksString,
                            type='vector')
        # TODO: If masks are temporary, delete them


def copy_georeferencing(imagesDir, masksDir, maskFileName, refExtension,
                        referencing):
    r2 = os.path.join(masksDir, maskFileName + refExtension)
    copyfile(os.path.join(imagesDir, referencing), r2)


if __name__ == "__main__":
    options, flags = gscript.parser()
    main(options, flags)

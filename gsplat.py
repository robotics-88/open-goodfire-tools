import argparse
import subprocess
from pathlib import Path
import time

import utils.argument_actions

import docker
import docker.types

from fastlog import log

log_level_options = [log.WARNING, log.INFO, log.DEBUG]


def run_in_docker(command, image, mounts):
    # TODO: consider capping nvidia clock speeds, lest the computer crash
    # sudo nvidia-smi -lgc 300,1500

    # TODO: design graceful exit - stop the container if the script is interrupted

    client = docker.from_env()
    gpu_device = docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])

    container = client.containers.run(image, command, auto_remove=True, runtime='nvidia', detach=True, device_requests=[gpu_device], mounts=mounts, environment={'PYTORCH_CUDA_ALLOC_CONF':'expandable_segments:True'})
    log_stream = container.attach(stream=True, logs=True)
    container.start()

    # TODO: make a fastlog pipe so I don't have to do these shenanigans



    # --- LOGGING ---
    # A given element from the log stream may include any number of newlines
    # Each newline should correspond to exactly one log statement
    # Lastly, an element may not start or end with a newline, leaving a remnant that should be concatenated with the beginning of the next element
    
    remnant = ''
    for log_line in log_stream:
        # Split on newline
        fragments = log_line.decode().split('\n')

        # Print the leftover log line
        log.debug(remnant + fragments.pop(0))
        
        # Save the last fragment of this element; it must not be newline terminated, and thus should not be printed yet
        if len(fragments):
            remnant = fragments.pop()
        else:
            remnant = ''

        # Print the remaining log lines
        for fragment in fragments:
            log.debug(fragment)


def generate_images(video_path, images_path, sample_rate, image_name_pattern):
    images_path.mkdir(parents=True, exist_ok=True)
    # TODO: catch stdout in fastlog.debug
    return subprocess.call(['ffmpeg', '-i', video_path, '-vf', f'fps={sample_rate}', images_path / image_name_pattern])


def generate_sfm_colmap(images_path, database_path, sparse_path):
    sparse_path.mkdir(parents=True, exist_ok=True)
    database_path.touch(exist_ok=True)

    images_mount = docker.types.Mount('/data/images', str(images_path.absolute()), type='bind')
    sparse_mount = docker.types.Mount('/data/sparse', str(sparse_path.absolute()), type='bind')
    db_mount = docker.types.Mount('/data/database.db', str(database_path.absolute()), type='bind')

    # TODO: pull first, make logs visible    
    with log.indent():
        log.info('running feature extraction...')
        with log.indent():
            feature_extraction_command = 'colmap feature_extractor --database_path /data/database.db --image_path /data/images'
            run_in_docker(feature_extraction_command, 'colmap/colmap:latest', [images_mount, sparse_mount, db_mount])

        log.info('running matcher...')
        with log.indent():
            matcher_command = 'colmap exhaustive_matcher --database_path /data/database.db'
            run_in_docker(matcher_command, 'colmap/colmap:latest', [images_mount, sparse_mount, db_mount])

        log.info('running mapper...')
        with log.indent():
            mapper_command = 'colmap mapper --database_path /data/database.db --image_path /data/images --output_path /data/sparse'
            run_in_docker(mapper_command, 'colmap/colmap:latest', [images_mount, sparse_mount, db_mount])


def generate_sfm_odm(images_path, opensfm_path):
    opensfm_path.mkdir(exist_ok=True)

    images_mount = docker.types.Mount('/data/images', str(images_path.absolute()), type='bind')
    odm_mount = docker.types.Mount('/data/opensfm', str(opensfm_path.absolute()), type='bind')

    # TODO: pull first, make logs visible    
    log.info('running odm...')
    with log.indent():
        odm_command = '--project-path / data --skip-orthophoto --skip-report --matcher-neighbors 7 --matcher-order 7'
        run_in_docker(odm_command, 'opendronemap/odm', [images_mount, odm_mount])


def generate_sfm_mvg(images_path, openmvg_path, geo_method='non-rigid', geo_matching=False, matching_neighbors=5):
    camera_database_path = Path('depend/openMVG/src/openMVG/exif/sensor_width_database/sensor_width_camera_database.txt')
    openmvg_binary_path = Path('depend/openMVG/build/Linux-x86_64-RELEASE')
    matches_path = openmvg_path / 'matches'
    reconstruction_path = openmvg_path / 'incremental'

    matches_path.mkdir(parents=True, exist_ok=True)
    reconstruction_path.mkdir(parents=True, exist_ok=True)

    json_path = openmvg_path / 'sfm_data.json'
    parilist_path = matches_path / 'pair_list.txt'
    
    with log.indent():
        log.info('List images...')
        # openMVG_main_SfMInit_ImageListing -d {camera_database_path} -i {images_path} -o matches -x 2400
        image_list_command = [openmvg_binary_path / 'openMVG_main_SfMInit_ImageListing', '-d', camera_database_path, '-i', images_path, '-o', openmvg_path, '-f', '2400']
        if geo_method == 'non-rigid':
            image_list_command.extend(['-P, --gps_to_xyz_method', '1'])
        subprocess.call(image_list_command)
        
        log.info('Compute Features...')
        # openMVG_main_ComputeFeatures -i matches/sfm_data.json -o matches
        subprocess.call([openmvg_binary_path / 'openMVG_main_ComputeFeatures', '-i', json_path, '-o', matches_path ])
        
        # openMVG_main_ListMatchingPairs -G -n 5 -i Dataset/matching/sfm_data.bin -o Dataset/matching/pair_list.txt
        log.info(f'List Pairs from {"GPS Exif" if geo_matching else "Video Adjacency"} Data...')
        pair_list_command = [openmvg_binary_path / 'openMVG_main_ListMatchingPairs', '-i', json_path, '-o', parilist_path]
        if geo_method == 'non-rigid':
            pair_list_command.extend(['-G', '-n', matching_neighbors])            
        else:
            pair_list_command.extend(['-V', '-n', matching_neighbors])
        subprocess.call(pair_list_command)
        

        log.info('Compute Matches...')
        # openMVG_main_ComputeMatches -i matches/sfm_data.json -o matches
        subprocess.call([openmvg_binary_path / 'openMVG_main_ComputeMatches', '-i', json_path, '-o', matches_path / 'matches.putative.bin'])

        log.info('Filter Matches...')
        subprocess.call([openmvg_binary_path / 'openMVG_main_GeometricFilter', '-i', json_path, '-m', matches_path / 'matches.putative.bin' , '-g' , 'f' , '-o' , matches_path / 'matches.f.bin' ] )


        log.info('Run SFM...')
        # openMVG_main_SfM -i matches/sfm_data.json -m matches -o reconstruction -s INCREMENTAL
        sfm_command = [openmvg_binary_path / 'openMVG_main_SfM', '-i', json_path, '-m', matches_path, '-o', reconstruction_path, '-s', 'INCREMENTAL']
        if geo_method == 'non-rigid':
            sfm_command.extend(['-P'])
        subprocess.call(sfm_command)


        if geo_method == 'rigid':

            log.info('Do GPS Transformation...')
            # openMVG_main_geodesy_registration_to_gps_position -i Dataset/out_Reconstruction/sfm_data.bin -o Dataset/out_Reconstruction/sfm_data_adjusted.bin
            subprocess.call([openmvg_binary_path / 'openMVG_main_geodesy_registration_to_gps_position', '-i', json_path, '-o', openmvg_path / 'sfm_data_adjusted.json'])
            json_path = openmvg_path / 'sfm_data_adjusted.json'


        log.info('Colorize...')
        # openMVG_main_ComputeSfM_DataColor -i reconstruction/incremental/sfm_data.bin -o reconstruction/colorized.ply
        subprocess.call([openmvg_binary_path / 'openMVG_main_ComputeSfM_DataColor', '-i', json_path, '-o', reconstruction_path / 'colorized.ply'])

    

def generate_ply(mounts, num_splats):
    client = docker.from_env()

    # Check that our custom image exists
    image_exists = False
    for image in client.images.list():
        if 'open_splat:latest' in image.tags:
            image_exists = True
            break
    
    # Build the image
    if not image_exists:
        log.info('Building opensplat image. This may take a while...')
        # TODO: Logs
        client.images.build(path='depend/OpenSplat', tag='open_splat:latest')
    
    ply_path.touch(exist_ok=True)

    # Run the image
    
    log.info('running opensplat')
    with log.indent():
        open_splat_command = f'/code/build/opensplat /data -n {num_splats} -o /data/output.splat'
        run_in_docker(open_splat_command, 'open_splat:latest', mounts=mounts)


if __name__ == '__main__':
    sfm_options = {
        'colmap': generate_sfm_colmap,
        'odm': generate_sfm_odm,
        'mvg': generate_sfm_mvg
    }


    parser = argparse.ArgumentParser()

    parser.add_argument('--dataset', type=str, required=True)
    parser.add_argument('--sfm', choices=sfm_options.keys())

    parser.add_argument('-v', action='count')
    parser.add_argument('--verbosity', type=int, default=1)

    args = parser.parse_args()

    # Process verbosity args
    verbosity = args.v if args.v else args.verbosity
    verbosity = min(verbosity, len(log_level_options)-1)
    log.setLevel(log_level_options[verbosity])


    video_path = Path(f'gsplat_data/input/{args.dataset}.mp4')
    output_path = Path(f'gsplat_data/output/{args.dataset}')

    images_path =       output_path / 'images'

    sparse_path =       output_path / 'sparse'
    database_path =     output_path / 'database.db'
    
    odm_path =          output_path / 'odm'
    mvg_path =          output_path / 'mvg'
    
    openmvg_path =      output_path / 'reconstruction'
    
    ply_path =          output_path / 'splat.ply'


    # FFMPEG
    # TODO: this step will need to do EXIF data tagging as well. TBD how we will transmit that info. Likely it will be encoded as subtitles
    # TODO: ODM may be able to handle EXIF tagging
    tic = time.time()
    if images_path.exists():
        log.info(f'Skipping - Image Sampling: already exists at {images_path}')
    else:
        log.info(f'Running Image Sampling at {images_path}')
        generate_images(video_path, images_path, 5, "out%d.png")
    generate_images_time = time.time() - tic

    # SFM
    tic = time.time()
    if args.sfm == 'colmap':
        if sparse_path.exists():
            log.info(f'Skipping - SFM: already exists at {sparse_path}')
        else:
            log.info(f'Running {args.sfm} at {sparse_path}')
            generate_sfm_colmap(images_path, database_path, sparse_path)

    elif args.sfm == 'odm':
        if odm_path.exists():
            log.info(f'Skipping - SFM: already exists at {odm_path}')
        else:
            log.info(f'Running {args.sfm} at {odm_path}')
            generate_sfm_odm(images_path, odm_path)
    
    elif args.sfm == 'mvg':
        # if mvg_path.exists():
        #     log.info(f'Skipping - SFM: already exists at {mvg_path}')
        # else:
        log.info(f'Running {args.sfm} at {mvg_path}')
        generate_sfm_mvg(images_path, mvg_path)
    generate_sparse_time = time.time() - tic


    # PLY
    tic = time.time()
    if ply_path.exists():
        log.info(f'Skipping - OpenSplat: already exists at {ply_path}')
    else:
        log.info(f'Running OpenSplat at {ply_path}')

        mounts = [
            docker.types.Mount('/data/images', str(images_path.absolute()), type='bind'),
            docker.types.Mount('/data/output.splat', str(ply_path.absolute()), type='bind')
        ]

        if args.sfm == 'colmap':
            mounts.append(docker.types.Mount('/data/sparse', str(sparse_path.absolute()), type='bind'))

        elif args.sfm == 'odm':
            mounts.append(docker.types.Mount('/data/opensfm', str(odm_path.absolute()), type='bind'))

        # elif args.sfm == 'openMVG':
        #    mounts.append(docker.types.Mount('/data/reconstruction', str(openmvg_path.absolute()), type='bind'))

        generate_ply(mounts, 100_000)
    generate_ply_time = time.time() - tic


    # REPORTING
    log.info(f'generate_images_time: {generate_images_time:.2f}')
    log.info(f'generate_sparse_time: {generate_sparse_time:.2f}')
    log.info(f'generate_ply_time:    {generate_ply_time:.2f}')
    log.info(f'total time elapsed:   {(generate_images_time + generate_sparse_time + generate_ply_time):.2f}')
    log.info(f'ply is at:            {ply_path}')
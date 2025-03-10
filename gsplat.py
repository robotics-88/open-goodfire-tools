import argparse
import subprocess

import docker
import docker.types

from pathlib import Path

import time

def generate_images(video_path, images_path, sample_rate, image_name_pattern):
    images_path.mkdir(parents=True, exist_ok=True)
    return subprocess.call(['ffmpeg', '-i', video_path, '-vf', f'fps={sample_rate}', images_path / image_name_pattern])

def generate_sparse(images_path, database_path, sparse_path):
    # TODO: bind mount the database, if we need it
    client = docker.from_env()

    sparse_path.mkdir(parents=True, exist_ok=True)
    database_path.touch(exist_ok=True)

    images_mount = docker.types.Mount('/data/images', str(images_path.absolute()), type='bind')
    sparse_mount = docker.types.Mount('/data/sparse', str(sparse_path.absolute()), type='bind')
    db_mount = docker.types.Mount('/data/database.db', str(database_path.absolute()), type='bind')

    

    feature_extraction_command = 'colmap feature_extractor --database_path /data/database.db --image_path /data/images'
    matcher_command = 'colmap exhaustive_matcher --database_path /data/database.db'
    mapper_command = 'colmap mapper --database_path /data/database.db --image_path /data/images --output_path /data/sparse'

    # TODO: pull first, make logs visible
    gpu_device = docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
    device_requests=[gpu_device]

    # TODO: consider capping nvidia clock speeds, lest the computer crash
    # sudo nvidia-smi -lgc 300,1500

    # colmap_container = client.containers.run('colmap/colmap:latest', 'sleep infinity', auto_remove=False, detach=True, mounts=[images_mount, sparse_mount, db_mount])
    print('running feature extraction...')
    colmap_container = client.containers.run('colmap/colmap:latest', feature_extraction_command, auto_remove=True, runtime='nvidia', detach=True, device_requests=[gpu_device], mounts=[images_mount, sparse_mount, db_mount])

    log_stream = colmap_container.attach(stream=True, logs=True)
    colmap_container.start()
    for log_line in log_stream:
        print(str(log_line))

    print('running matcher...')
    colmap_container = client.containers.run('colmap/colmap:latest', matcher_command, auto_remove=True, runtime='nvidia', detach=True, device_requests=[gpu_device], mounts=[images_mount, sparse_mount, db_mount])

    log_stream = colmap_container.attach(stream=True, logs=True)
    colmap_container.start()
    for log_line in log_stream:
        print(str(log_line))

    print('running mapper...')
    colmap_container = client.containers.run('colmap/colmap:latest', mapper_command, auto_remove=True, runtime='nvidia', detach=True, device_requests=[gpu_device], mounts=[images_mount, sparse_mount, db_mount])

    log_stream = colmap_container.attach(stream=True, logs=True)
    colmap_container.start()
    for log_line in log_stream:
        print(str(log_line))

    # print('running feature extraction...')
    # colmap_container.exec_run(feature_extraction_command)
    # print('running matcher...')
    # colmap_container.exec_run(matcher_command)
    # print('running mapper...')
    # colmap_container.exec_run(mapper_command)

    # colmap_container.kill()
    # colmap_container.remove(force=True)
    

def generate_ply(images_path, sparse_path, ply_path, num_splats):
    client = docker.from_env()

    # Check that our custom image exists
    image_exists = False
    for image in client.images.list():
        if 'open_splat:latest' in image.tags:
            image_exists = True
            break
    
    # Build the image
    if not image_exists:
        print('building image...')
        client.images.build(path='depend/OpenSplat', tag='open_splat:latest')
    
    ply_path.touch(exist_ok=True)

    # Run the image
    images_mount = docker.types.Mount('/data/images', str(images_path.absolute()), type='bind')
    sparse_mount = docker.types.Mount('/data/sparse', str(sparse_path.absolute()), type='bind')
    db_mount = docker.types.Mount('/data/output.splat', str(ply_path.absolute()), type='bind')
    gpu_device = docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
    
    
    print('running opensplat')
    container = client.containers.run('open_splat:latest', f'/code/build/opensplat /data -n {num_splats} -o /data/output.splat', auto_remove=True, runtime='nvidia', device_requests=[gpu_device], mounts=[images_mount, sparse_mount, db_mount], detach=True)
    # container = client.containers.create('open_splat:latest', 'echo hello1 && sleep 1 && echo hello2', privileged=True, runtime='nvidia', mounts=[images_mount, sparse_mount, db_mount], detach=True)
    log_stream = container.attach(stream=True, logs=True)
    container.start()
    for log_line in log_stream:
        print(str(log_line))
    # container.remove()


if __name__ == '__main__':
    video_path = Path('gsplat_data/input/gopro/trimmed.mp4')
    images_path = Path('gsplat_data/output/gopro/input')
    sparse_path = Path('gsplat_data/output/gopro/sparse')
    database_path = Path('gsplat_data/output/gopro/database.db')
    ply_path = Path('gsplat_data/output/gopro/splat.ply')

    tic = time.time()
    if not images_path.exists():
        generate_images(video_path, images_path, 5, "out%d.png")
    
    generate_images_time = time.time() - tic

    tic = time.time()
    if not sparse_path.exists():
        generate_sparse(images_path, database_path, sparse_path)
    generate_sparse_time = time.time() - tic

    tic = time.time()
    if not ply_path.exists():
        generate_ply(images_path, sparse_path, ply_path, 100_00)
    generate_ply_time = time.time() - tic

    print(f'generate_images_time: {generate_images_time:.2f}')
    print(f'generate_sparse_time: {generate_sparse_time:.2f}')
    print(f'generate_ply_time:    {generate_ply_time:.2f}')
    print(f'total time elapsed:   {(generate_images_time + generate_sparse_time + generate_ply_time):.2f}')
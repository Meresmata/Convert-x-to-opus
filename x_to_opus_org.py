# import multiprocessing as mp
import getpass
import multiprocessing.dummy as mp_thread
import os
import subprocess
import typing as tp

import ffmpy


def isvideo(file: str)->bool:
    """
    test whether param file is has a known ending for video formats
    :param file: str
    :return: bool
    """
    video_files = ["avi", "mp4", "webm"]
    end = file.rsplit(".", 1)[-1]
    return True if end in video_files else False


def isaudio(file: str)->bool:
    """
    test whether param file is has a known ending for audio formats
    :param file: str
    :return: bool
    """
    audio_files = ["mp3", "aac", "ogg", "m4a"]
    end = file.rsplit(".", 1)[-1]
    return True if end in audio_files else False


def create_io_struct_list(in_files: list, start_name_fn: tp.Any, end_name_fn: tp.Any,
                         out_path_dir: tp.Optional[str])->list:
    """
    create a list containing a list of in and out file names
    :type in_files: list
    :type start_name_fn: function
    :type end_name_fn: function
    :type out_path_dir: str
    :return: list
    """
    media_files = list(filter(lambda x: (isaudio(x) or isvideo(x)) and os.path.isfile(x), in_files))
    return [[x, end_name_fn(start_name_fn(x, out_path_dir), ".ogg", ".opus"), False] for x in media_files]


def convert(pool_map_tuple: tuple)->None:
    """
    Does the actual conversion
    :param pool_map_tuple: tuple of list(input file name, output filename, conversion flag),
     function for codex, function for bit rate
    :return: None
    """
    # unpack
    file, codec_fn, bit_rate_fn = pool_map_tuple
    # calculate the bit_rate_fn bit rate for the new file
    out_bit_rate: int = 0
    in_bit_rate = bit_rate_fn(file[0])
    in_codec = codec_fn(file[0])
    if codec_fn(file[0]) == "vorbis" or "aac":
        out_bit_rate = (lambda x: 54000 if x <= 64001 else 64000)(in_bit_rate)
    else:
        out_bit_rate = (lambda x: 54000 if x <= 100001 else 64000)(in_bit_rate)

    if (in_bit_rate < out_bit_rate) or in_codec == "opus":
        return

    # set conversion flag
    file[2] = True

    # parse param for conversion
    o_command: str = '-v error -vn -vbr constrained -b:a ' + str(out_bit_rate) + \
                     ' -compression_level 10 -acodec libopus'
    ff = ffmpy.FFmpeg(
        inputs={file[0]: None},
        outputs={file[1]: o_command}
    )

    # convert
    ff.run()


def get_in_bit_rate(file: str)-> int:
    """
    Returns the bitrate of file with help of ffprobe
    :param file: str filename
    :return: int bit rate
    """
    p_command: str = "-v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1"
    probe = ffmpy.FFprobe(inputs={file: p_command})
    try:
        bit_rate = int((probe.run(stdout=subprocess.PIPE))[0])
    except ValueError:
        bit_rate = -1
    return bit_rate


def get_file_names(path: str)->list:
    """
    return a list with all files from root folder path
    :param path: str path to selected root folder
    :return: list
    """
    file_list: list = []
    for rootdir, subdirs, files in os.walk(path):
        for name in files:
            file_list.append(rootdir + r"/" + name)
    return file_list


def get_in_codec(file: str)-> str:
    """
    return the audio codec name of file
    :param file: str file name
    :return: str codex name
    """
    # https://github.com/Ch00k/ffmpy/blob/master/docs/examples.rst
    p_command = "-v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1"
    probe = ffmpy.FFprobe(inputs={file: p_command})
    return (probe.run(stdout=subprocess.PIPE))[0].strip()


def rename_ending(file: str, condition: str, ending: str)-> str:
    """
    conditional renaming of file name ending
    :param file: str file name
    :param condition: str file name ending to be compared with
    :param ending: str new ending
    :return: str
    """
    file_name = file.rsplit(".", 1)[0]
    return file_name + ending if file.endswith(condition) else file_name + condition


def rename_start(file: str, output_dir: tp.Optional[str])-> str:
    """
    rename of the root folder for output if that one has been specified
    :param file: str file name
    :param output_dir: str new root folder name, empty if nothing shall be done
    :return: str new name
    """
    return output_dir + file.rsplit("/", 1)[-1] if output_dir else file


if __name__ == '__main__':
    """
    changes audio and video files to .opus files only
    in specified directory and all it's subdirectories
    """
    p_dir = "/home/" + getpass.getuser() + "/Downloads/Hörbücher"
    out_dir: str = None

    # files will contain all files to be changed
    # structure list of (in_file_name, out_filename, conversion_flag)
    all_files = get_file_names(p_dir)
    in_out_files: list = create_io_struct_list(all_files, rename_start, rename_ending, out_dir)

    # sorting files?

    # doing the slow stuff in parallel

    # http.//chriskiehl.com/article-parallelism-in-one-line/
    # open Pool with mp_thread.cpu_count() cores
    pool = mp_thread.Pool()

    # pool.map can only work on one iterable
    # create on iterable
    pool_iterable = [(x, get_in_codec, get_in_bit_rate) for x in in_out_files]
    pool.map(convert, pool_iterable)
    pool.close()
    pool.join()

    # return to serial processing
    # delete all files that have been converted
    [os.remove(x[0]) for x in list(filter(lambda x: x[2], in_out_files))]
    # prepare renaming
    left_list = list(filter(lambda x: (isvideo(x) or isaudio(x)) and os.path.isfile(x), get_file_names(p_dir)))
    file_num = len(left_list)
    name_list = map(rename_ending, left_list, [".opus"]*file_num, [".ogg"]*file_num)

    # rename
    map(lambda x: os.rename(x[0]), name_list)

import concurrent.futures as cf
import os
import os.path as p
import subprocess
import ffmpy
import argparse
import typing as tp

"""
convertes all audio, movie files
of a given root directory into .opus

requires: ffmpeg incl. libopus
"""


def convert(file: str)->bool:
    """
    Does the actual conversion
    :param file: str of the filename
    :return: bool: is converted?
    """

    # calculate the bit_rate_fn bit rate for the new file
    in_bit_rate = get_in_bit_rate(file)

    # for codex with higher performances, do not reduce bitrate so strongly
    if any([x in get_audio_codec(file) for x in (b"vorbis", b"aac", b"opus")]):
        if in_bit_rate < 54000:
            out_bit_rate = in_bit_rate
        elif in_bit_rate <= 64000:
            out_bit_rate = 54000
        else:
            out_bit_rate = 64000
    else:
        if in_bit_rate < 16000:
            out_bit_rate = in_bit_rate
        elif in_bit_rate <= 32000:
            out_bit_rate = 16000
        elif in_bit_rate <= 48000:
            out_bit_rate = 32000
        elif in_bit_rate <= 10000:
            out_bit_rate = 54000
        else:
            out_bit_rate = 64000

    # parse param for conversion
    o_command: str = '-v error -vn -vbr constrained -b:a ' + str(out_bit_rate) + \
                     ' -compression_level 10 -acodec libopus'

    ff = ffmpy.FFmpeg(
        inputs={file: None},
        outputs={rename(file, out_dir): o_command}
    )

    # convert
    try:
        ff.run()
        return True
    except ffmpy.FFRuntimeError:
        return False


def _get_ffprobe(file: str, command: str)->tp.Any:
    """
    Returns the bitrate of file with help of ffprobe
    :param file: str, filename
    :param command: str, command for probing
    :return: retrieved value from probe
    """
    probe = ffmpy.FFprobe(inputs={file: command})
    try:
        query = probe.run(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except ffmpy.FFRuntimeError:
        return None
    except ffmpy.FFExecutableNotFoundError:
        return None
    else:
        return query[0]


def get_in_bit_rate(file: str)-> tp.Optional[int]:
    """
    Returns the bitrate of file with help of ffprobe
    :param file: str filename
    :return: int bit rate
    """
    p_command: str = "-v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1"
    ret_val = _get_ffprobe(file, p_command)
    try:
        return int(ret_val) if ret_val else None
    except ValueError:
        return None


def get_file_names(path: str)->list:
    """
    return a list with all files from root folder path
    :param path: str path to selected root folder
    :return: list
    """
    files_: list = []
    for root_dir, _, files in os.walk(path):
        for name in files:
            files_.append(root_dir + r"/" + name)
    return files_


class Memorize:
    """
    Memorization
    :param f: function name
    :return: Any (Anything)
    """
    def __init__(self, f):
        self.f = f
        self.memo = {}

    def __call__(self, *args):
        if args not in self.memo:
            self.memo[args] = self.f(*args)
        return self.memo[args]


@Memorize
def get_audio_codec(file: str)-> tp.Optional[str]:
    """
    return the audio codec name of file
    :param file: str file name
    :return: str codex name
    """
    # https://github.com/Ch00k/ffmpy/blob/master/docs/examples.rst
    p_command = "-v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1"
    ret_val = _get_ffprobe(file, p_command)
    return ret_val.strip() if ret_val else None


def get_video_codec(file: str)-> tp.Optional[str]:
    """
    return the audio codec name of file
    :param file: str file name
    :return: str codex name
    """
    # https://github.com/Ch00k/ffmpy/blob/master/docs/examples.rst
    p_command = "-v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1"
    ret_val = _get_ffprobe(file, p_command)
    return ret_val.strip() if ret_val else None


@Memorize
def get_duration(file: str)->tp.Optional[float]:
    """
    :return the length of media file in seconds
    :param file: str Name of the file
    :return: int duration in seconds
    """
    p_command: str = "-v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1"
    ret_val = _get_ffprobe(file, p_command)

    return float(ret_val) if ret_val else None


def rename(file: str, new_path: str)-> str:
    """
    conditional renaming of file name ending
    :param file: str file name
    :param new_path: new name of the path
    :return: str
    """

    def fsplit(x: str)->str:
        return x.rsplit(".", 1)[0]

    file_name = fsplit(p.basename(file))
    return p.join(new_path, file_name, ".opus") if new_path else p.join(fsplit(file) + ".opus")


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str, help='Path to the main folder of files.')
    parser.add_argument('-o', '--output', type=str,
                        help='Path to the main output folder. Default same as input with override', default=None)
    return parser.parse_args()


if __name__ == '__main__':
    """
    changes audio and video files to .opus files only
    in specified directory and all it's subdirectories
    """
    arguments = parse_arguments()
    p_dir = arguments.path
    out_dir = arguments.output

    # files will contain all files to be changed
    # structure list of (in_file_name, out_filename, conversion_flag)
    in_files = get_file_names(p_dir)

    # doing the slow stuff in parallel
    # http.//chriskiehl.com/article-parallelism-in-one-line/
    # open Pool with mp_thread.cpu_count() cores

    with cf.ThreadPoolExecutor() as executor:
        file_dict = dict(
            zip(in_files, list(executor.map(get_audio_codec, in_files))))

    # deselect all cases that, do are not needed to be converted
    # has no audio, or audio is already opus(that has no video)
    file_set = {k for (k, v) in file_dict.items() if v}
    opus_set = {k for (k, v) in file_dict.items() if v == b"opus" and not get_video_codec(k)}
    file_list = list(file_set - opus_set)

    # convert
    # test whether all important facts are known?
    with cf.ThreadPoolExecutor() as executor:
        length_dict = dict(zip(file_list, list(executor.map(get_duration, file_list))))
        length_list = [k for (k, v) in length_dict.items() if v]

        rate_dict = dict(zip(file_list, list(executor.map(get_in_bit_rate, file_list))))
        rate_list = [k for (k, v) in rate_dict.items() if v]

        is_converted_dict = dict(zip(length_list, list(executor.map(convert, rate_list))))

    # delete all files that have been converted
    # for all converted files test whether converted successfully (files lengths old vs new almost equal?)
    # yes: delete old, no: delete new
    [os.remove(k)
     if abs(get_duration(k) - get_duration(rename(k, out_dir))) - 0.1 < 0.0
     else os.remove(rename(k, out_dir))
     for (k, v) in is_converted_dict.items() if v]

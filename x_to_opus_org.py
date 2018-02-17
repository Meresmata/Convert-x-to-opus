import os
import ffmpy
import subprocess
import multiprocessing.dummy as mp_thread
# import multiprocessing as mp
import getpass


def isvideo(file: str):
    """

    :param file: str
    :return: bool
    """
    video_files = ["avi", "mp4", "webm"]
    end = file.rsplit(".", 1)[-1]
    if end in video_files:
        return True
    else:
        return False


def isaudio(file: str):
    """

    :param file: str
    :return: bool
    """
    audio_files = ["mp3", "aac", "ogg", "m4a"]
    end = file.rsplit(".", 1)[-1]
    if end in audio_files:
        return True
    else:
        return False


def create_audiofile_list(file_list: list, path_dir: str, sort_size: bool = False, sort_reverse: bool = False):
    """

    :type file_list: list
    :type path_dir: str
    :type sort_size: bool
    :type sort_reverse: bool
    :return: None
    """
    # for f in os.listdir(path_dir):
    #   path_name = path_dir + r"/" + f
    #    if os.path.isfile(path_name) and (isvideo(f) or isaudio(f)):
    #        file_list.append(path_name)

    for rootdir, subdirs, files in os.walk(path_dir):
        for name in files:
            path_name = rootdir + r"/" + name
            if os.path.isfile(path_name) and (isvideo(name) or isaudio(name)):
                file_list.append(path_name)

    if sort_size:
        file_list.sort(key=os.path.getsize, reverse=sort_reverse)
    else:
        file_list.sort(key=str.lower, reverse=sort_reverse)
    pass


def convert(file: str):
    """

    :param file: str
    :return: None
    """


    p_command: str = "-v error -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1"
    probe = ffmpy.FFprobe(inputs={file: p_command})
    try:
        bit_rate = int((probe.run(stdout=subprocess.PIPE))[0])
    except Exception:
        return

    # https://github.com/Ch00k/ffmpy/blob/master/docs/examples.rst
    p_command = "-v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1"
    probe = ffmpy.FFprobe(inputs={file: p_command})
    codec = (probe.run(stdout=subprocess.PIPE))[0].strip()

    # calculate the bit rate for the new file
    out_bit_rate: int = 0
    if codec == "vorbis" or "aac":
        out_bit_rate = (lambda x: 54000 if x <= 64001 else 64000)(bit_rate)
    else:
        out_bit_rate = (lambda x: 54000 if x <= 100001 else 64000)(bit_rate)

    if bit_rate < out_bit_rate:
        out_bit_rate = bit_rate

    # convert into new filename, incl. new folder
    outfilename = file.rsplit(".", 1)[0] + ".ogg"

    # if ending is .ogg but opus as codec
    if outfilename == file:
        outfilename = file.rsplit(".", 1)[0] + ".opus"

    # if output directory is specified
    if out_dir is not None:
        outfilename = out_dir + r"/" + outfilename.rsplit(r"/", 1)[-1]

    # convert if not already done
    if codec != "opus":
        o_command: str = '-v error -vn -vbr on -b:a ' + str(out_bit_rate) + ' -compression_level 10 -acodec libopus'
        ff = ffmpy.FFmpeg(
            inputs={file: None},
            outputs={outfilename: o_command}
        )

        ff.run()
        os.remove(file)
        if outfilename.endswith(".opus"):
            os.rename(outfilename, outfilename.rsplit(".", 1)[0] + ".ogg")


if __name__ == '__main__':
    """
    changes audio and video files to .opus files only
    in specified directory and all it's subdirectories
    """
    p_dir = "/home/" + getpass.getuser() + "/Downloads"

    out_dir = None

    # files will contain all files to be changed
    files: list = []

    create_audiofile_list(files, p_dir, False, True)

    # http.//chriskiehl.com/article-parallelism-in-one-line/
    # open Pool with one process less than cores, one less than standard
    # pool = mp_thread.Pool(mp.cpu_count()-1)
    pool = mp_thread.Pool()
    pool.map(convert, files)

    pool.close()
    pool.join()

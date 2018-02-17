import os
import ffmpy
import subprocess
import multiprocessing.dummy as mp_thread
# import multiprocessing as mp
import tkinter as tk
import getpass
"""
convertes all audio, movie files
of a given root directory into .opus

requires: ffmpeg incl. libopus
"""

def isvideo(file: str):
    """
    compares with known video files format endings
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
    compares with known audio files format endings
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
    create list of files to be converted
    sort with respect to size, or name
    sort descending, or undescending
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
        """
        get files root folder
        """
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
    convertes video/audio files into opus only
    :param file: str
    :return: None
    """
    if dst_opt_check_val.get():
        o_dir = dst_folder_val.get()
    else:
        o_dir = None

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
    if o_dir is not None:
        outfilename = o_dir + r"/" + outfilename.rsplit(r"/", 1)[-1]

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

    done.set(done.get()+1)


def opt_act(event):
    """
    shall enable/disable output directory choice
    depending on Checkbox value
    :param event: event
    :return: None
    """
    if not dst_opt_check_val.get():

        dst_label.config(state='active')
        dst_folder.config(state='normal')
    else:
        dst_label.config(state='disabled')
        dst_folder.config(state='disabled')


def p_dir_act(event):
    """
    Action converts and checks input/root directory ony validity
    :param event: event
    :return: None
    """
    p_dir = src_folder.get()

    if p_dir.startswith("~"):
        p_dir = r"/home/" + getpass.getuser() + r"/" + p_dir.split("/", 1)[-1]
        src_dir_val.set(p_dir)
    assert os.path.isdir(p_dir)


def start_act(event):
    """
    Action: Start of retrieving files and convertion
    :param event: event
    :return: None
    """
    try:
        p_dir_act(event)
    except AssertionError:
        top = tk.Toplevel()
        top.title("Order")

        err_msg: str = 'Der Quellordner: "' + src_folder.get() + '" ist kein Ordner!'
        msg = tk.Message(top, text=err_msg)
        msg.pack()

        msg_button = tk.Button(top, text="Ok", command=top.destroy)
        msg_button.pack()
        return

    if dst_opt_check_val.get():
        try:
            o_dir_act(event)
        except AssertionError:
            top = tk.Toplevel()
            top.title("Order")

            err_msg = 'Der Zielordner"' + src_folder.get() + '" ist kein Ordner'
            msg = tk.Message(top, text=err_msg)
            msg.pack()
            msg_button = tk.Button(top, text="Ok", command=top.destroy)
            msg_button.pack()

    start_button.config(state='disabled')
    p_dir = src_folder.get()

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


def ratio_act(event):
    """
    Action: calculate + refresh ratio of converted files
    DOES NOT WORK
    :param event: event
    :return: None
    """
    ratio.config(text=str(done.get()) + r"/" + str(file_num.get()))


def o_dir_act(event):
    """
    Action converts and checks output directory ony validity
    :param event: event
    :return: None
    """
    out_dir = dst_folder_val.get()

    if out_dir.startswith("~"):
        out_dir = r"/home/" + getpass.getuser() + r"/" + out_dir.split("/", 1)[-1]
        dst_folder_val.set(out_dir)

    assert os.path.isdir(out_dir)


if __name__ == '__main__':
    """
    changes audio and video files to .opus files only
    in specified directory and all it's subdirectories
    """
    # Tkinter gui description:

    root = tk.Tk()
    root.title("x to opus - Folder Conversion")
    root.resizable(0, 0)

    # label & Entry to ask for source folder
    src_label = tk.Label(root, text="Quellorder:")
    src_label.grid(row=0, column=0, sticky="w")

    src_dir_val = tk.StringVar()
    src_folder = tk.Entry(root, textvariable=src_dir_val)
    src_folder.grid(row=0, column=1)

    # Checkbox etc. to ask whether output directory is specified
    dst_opt_check_val = tk.IntVar()
    dst_opt_check = tk.Checkbutton(root, text="Ausgabeordner", variable=dst_opt_check_val, onvalue=1, offvalue=0)
    dst_opt_check.grid(row=1, column=0)
    dst_opt_check.bind("<Button-1>", opt_act)

    # label & Entry to ask for output folder
    dst_label = tk.Label(root, text="Zielordner:", state='disable')
    dst_label.grid(row=2, column=0, sticky="w")

    dst_folder_val = tk.StringVar()
    dst_folder = tk.Entry(root, state='disabled', textvariable=dst_folder_val)
    dst_folder.grid(row=2, column=1)

    # start button for the conversion process
    start_button = tk.Button(root, text="start encoding")
    start_button.grid(row=3, column=2, sticky="se")
    start_button.bind("<Button-1>", start_act)

    # Label to show how many files been converted
    # functionally does not work
    ratio = tk.Label(root)
    ratio.grid(row=3, column=0, sticky="sw")

    done = tk.IntVar()
    done.set(0)
    done.trace("w", ratio_act)

    file_num = tk.IntVar(value=0)

    # start
    root.mainloop()

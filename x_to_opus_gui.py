import os
import ffmpy
import subprocess
import multiprocessing.dummy as mp_thread
# import multiprocessing as mp
import tkinter as tk
import getpass
import typing as tp
"""
convertes all audio, movie files
of a given root directory into .opus

requires: ffmpeg incl. libopus
"""


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


def create_io_struct_list(in_files: list, start_name_fn: tp.Callable[[str, tp.Optional[str]], str],
                          end_name_fn: tp.Callable[[str, str, str], str], out_path_dir: tp.Optional[str])->list:
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


class Application(tk.Frame):
    """
    A GUI for the conversion
    """
    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.grid()

        # create attributes
        # for getting source folder
        self.src_label = tk.Label(self.master, text="Quellorder:")
        self.src_dir_val = tk.StringVar()
        self.src_folder = tk.Entry(self.master, textvariable=self.src_dir_val)

        # for getting destination folder
        self.dst_opt_check_val = tk.IntVar()
        self.dst_opt_check = tk.Checkbutton(self.master, text="Ausgabeordner selbst wählen?",
                                            variable=self.dst_opt_check_val, onvalue=1, offvalue=0)
        self.dst_label = tk.Label(self.master, text="Ausgabeordner:", state='disable')
        self.dst_folder_val = tk.StringVar()
        self.dst_folder = tk.Entry(self.master, state='disabled', textvariable=self.dst_folder_val)

        self.ratio = tk.Label(self.master)
        self.start_button = tk.Button(self.master, text="start encoding")
        self.done = tk.IntVar()
        self.file_num = tk.IntVar(value=0)

        self.create_widgets()

    def create_widgets(self):
        # label & Entry to ask for source folder
        self.src_label.grid(row=0, column=0, sticky="w")
        self.src_folder.grid(row=0, column=1)

        # Checkbox etc. to ask whether output directory is specified
        self.dst_opt_check.grid(row=1, column=0)
        self.dst_opt_check.bind("<Button-1>", self.opt_act)

        # label & Entry to ask for output folder
        self.dst_label.grid(row=2, column=0, sticky="w")
        self.dst_folder.grid(row=2, column=1)

        # start button for the conversion process
        self.start_button.grid(row=3, column=2, sticky="se")
        self.start_button.bind("<Button-1>", self.start_act)

        # Label to show how many files been converted
        # functionally does not work
        self.ratio.grid(row=3, column=0, sticky="sw")

        self.done = tk.IntVar()
        self.done.set(0)
        self.done.trace("w", self.ratio_act)

    def start_act(self, event):
        """
        Action: Start of retrieving files and convertion
        :param event: event
        :return: None
        """
        try:
            self.p_dir_act(event)
        except AssertionError:
            top = tk.Toplevel()
            top.title("Order")

            err_msg: str = 'Der Quellordner: "' + self.src_folder.get() + '" ist kein Ordner!'
            msg = tk.Message(top, text=err_msg)
            msg.pack()

            msg_button = tk.Button(top, text="Ok", command=top.destroy)
            msg_button.pack()
            return

        if self.dst_opt_check_val.get():
            try:
                self.o_dir_act(event)
            except AssertionError:
                top = tk.Toplevel()
                top.title("Order")

                err_msg = 'Der Zielordner"' + self.src_folder.get() + '" ist kein Ordner'
                msg = tk.Message(top, text=err_msg)
                msg.pack()
                msg_button = tk.Button(top, text="Ok", command=top.destroy)
                msg_button.pack()

        self.start_button.config(state='disabled')
        p_dir = self.src_folder.get()

        # files will contain all files to be changed
        all_files = get_file_names(p_dir)
        in_out_files: list = create_io_struct_list(all_files, rename_start, rename_ending, str(self.dst_folder_val))

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
        name_list = map(lambda x: rename_ending(x, ".opus", ".ogg"), left_list)

        # rename
        map(lambda x, y: os.rename(x, y), left_list, name_list)

    def ratio_act(self, event):
        """
        Action: calculate + refresh ratio of converted files
        DOES NOT WORK
        :param event: event
        :return: None
        """
        self.ratio.config(text=str(self.done.get()) + r"/" + str(self.file_num.get()))

    def o_dir_act(self, event):
        """
        Action converts and checks output directory ony validity
        :param event: event
        :return: None
        """
        out_dir = self.dst_folder_val.get()

        if out_dir.startswith("~"):
            out_dir = r"/home/" + getpass.getuser() + r"/" + out_dir.split("/", 1)[-1]
            self.dst_folder_val.set(out_dir)

        assert os.path.isdir(out_dir)

    def opt_act(self, event):
        """
        shall enable/disable output directory choice
        depending on Checkbox value
        :param event: event
        :return: None
        """
        if not self.dst_opt_check_val.get():

            self.dst_label.config(state='active')
            self.dst_folder.config(state='normal')
        else:
            self.dst_label.config(state='disabled')
            self.dst_folder.config(state='disabled')

    def p_dir_act(self, event):
        """
        Action converts and checks input/root directory ony validity
        :param event: event
        :return: None
        """
        p_dir = self.src_folder.get()

        if p_dir.startswith("~"):
            p_dir = r"/home/" + getpass.getuser() + r"/" + p_dir.split("/", 1)[-1]
            self.src_dir_val.set(p_dir)
        assert os.path.isdir(p_dir)


if __name__ == '__main__':
    """
    changes audio and video files to .opus files only
    in specified directory and all it's subdirectories
    """
    # Tkinter gui description:

    app = Application()
    app.master.title("x to opus - Folder Conversion")
    app.master.resizable(0, 0)

    # start
    app.mainloop()

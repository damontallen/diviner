# -*- coding: utf-8 -*-
# file utilities for Diviner
from __future__ import print_function, division
import pandas as pd
import numpy as np
import sys
import glob
from dateutil.parser import parse as dateparser
from scipy import ndimage as nd
import divconstants as c
import os
from datetime import timedelta
from datetime import datetime as dt
# from plot_utils import ProgressBar
import zipfile

if sys.platform == 'darwin':
    datapath = '/Users/maye/data/diviner'
    kernelpath = '/Users/maye/data/spice/diviner'
else:
    datapath = '/raid1/maye/'
    kernelpath = '/raid1/maye/kernels'


###
### Tools for data output to tables
###

def prepare_write(Tb):
    Tb['year'] = Tb.index.year
    Tb['month'] = Tb.index.month
    Tb['day'] = Tb.index.day
    Tb['hour'] = Tb.index.hour
    Tb['minute'] = Tb.index.minute
    
    dtimes = Tb.index.to_pydatetime()
    
    
    Tb['second'] = ['.'.join([str(dt.second),str(dt.microsecond)]) for dt in dtimes]
    cols = Tb.columns
    time_cols = cols[-6:]
    dets = cols[:-6]
    new_cols = pd.Index(time_cols.tolist() + dets.tolist())
    return Tb.reindex(columns=new_cols)

class FileName(object):
    """Managing class for file name attributes """
    def __init__(self, fname):
        super(FileName, self).__init__()
        self.basename = os.path.basename(fname)
        self.dirname = os.path.dirname(fname)
        self.timestr= self.basename.split('_')[0]
        # save everything after the first '_' as rest
        self.rest = self.basename[self.basename.find('_'):]
        # split of the time elements
        self.year = self.timestr[:4]
        self.month = self.timestr[4:6]
        self.day = self.timestr[6:8]
        # if timestr is not long enough, self.hour will be empty string ''
        self.hour = self.timestr[8:10]
        # set time member
        self.set_time()
    
    def set_time(self):
        if len(self.timestr) == 8:
            format = '%Y%m%d'
        elif len(self.timestr) == 10:
            format = "%Y%m%d%H"
        else:
            format = '%Y%m%d%H%M'
        self.time = dt.strptime(self.timestr, format)
        self.format = format
    
    def get_previous_hour(self):
        return self.time - timedelta(hours=1)
        
    def set_previous_hour(self):
        newtime = self.get_previous_hour()
        self.time = newtime
        self.timestr = newtime.strftime(self.format)
        return self.fname
        
    def get_next_hour(self):
        return self.time + timedelta(hours=1)
        
    def set_next_hour(self):
        newtime = self.get_next_hour()
        self.time = newtime
        self.timestr = newtime.strftime(self.format)
        return self.fname
        
    @property
    def fname(self):
        return os.path.join(self.dirname, self.timestr + self.rest)
        
####
#### Tools for parsing text files of data
####


def split_by_n(seq, n):
    while seq:
        yield seq[:n]
        seq = seq[n:]


def timediff(s):
    return s - s.shift(1)


def parse_header_line(line):
    """Parse header lines.

    >>> s = ' a   b  c    '
    >>> parse_header_line(s)
    ['a', 'b', 'c']
    >>> s = '  a, b  ,   c '
    >>> parse_header_line(s)
    ['a', 'b', 'c']
    """
    line = line.strip('#')
    if ',' in line:
        newline = line.split(',')
    else:
        newline = line.split()
    return [i.strip() for i in newline]


def get_headers_pprint(fname):
    """Get headers from pprint output.

    >>> fname = '/Users/maye/data/diviner/noise2.tab'
    >>> headers = get_headers_pprint(fname)
    >>> headers[:7]
    ['date', 'month', 'year', 'hour', 'minute', 'second', 'jdate']
    """
    with open(fname) as f:
        headers = parse_header_line(f.readline())
    return headers


def get_rdr_headers(fname):
    """Get headers from both ops and PDS RDR files."""
    if isinstance(fname, zipfile.ZipFile):
        f = fname.open(fname.namelist()[0])
    else:
        f = open(fname)
    while True:
        line = f.readline()
        if not line.startswith('# Header'):
            break
    f.close()
    return parse_header_line(line)


def read_pprint(fname):
    """Read tabular diviner data into pandas data frame and return it.

    Lower level function. Use read_div_data which calls this as appropriate.
    """

    # pandas parser does not read this file correctly, but loadtxt does.
    # first will get the column headers

    headers = get_headers_pprint(fname)
    print("Found {0} headers: {1}".format(len(headers), headers))

    # use numpy's loadtxt to read the tabulated file into a numpy array
    ndata = np.loadtxt(fname, skiprows=1)
    dataframe = pd.DataFrame(ndata)
    dataframe.columns = headers
    dataframe.sort('jdate', inplace=True)
    return dataframe


def read_tabbed_rdr(fname, nrows=None):
    """Read tabular RDR files from opsRDR or the PDS."""
    if isinstance(fname, zipfile.ZipFile):
        name = fname.open(fname.namelist()[0])
    else:
        name = fname
    headers = get_rdr_headers(fname)
    df = pd.io.parsers.read_csv(name,
                                comment='#',
                                skipinitialspace=True,
                                names=headers,
                                na_values=['-9999.0'],
                                nrows=nrows,
                                parse_dates=[[0, 1]],
                                index_col=0,
                                )
    # the comment='#' does not skip line comments, but reads an empty
    # line that sets all fields to NaN. Dropping them here:
    return df.dropna(how='all')


def get_df_from_h5(fname):
    """Provide df from h5 file."""
    try:
        print("Opening {0}".format(fname))
        store = pd.HDFStore(fname)
        df = store[store.keys()[0]]
        store.close()
    except:
        print("file {0} not found.".format(fname))
    return df


def read_div_data(fname, **kwargs):
    with open(fname) as f:
        line = f.readline()
        if any(['dlre_edr.c' in line, 'Header' in line]):
            return read_tabbed_rdr(fname, **kwargs)
        elif fname.endswith('.h5'):
            return get_df_from_h5(fname)
        else:
            return read_pprint(fname)


####
#### tools for parsing binary data of Diviner
####


def parse_descriptor(fpath):
    f = open(fpath)
    lines = f.readlines()
    f.close()
    s = pd.Series(lines)
    s = s.drop(0)
    val = s[1]
    val2 = val.split(' ')
    [i.strip().strip("'") for i in val2]

    def unpack_str(value):
        val2 = value.split(' ')
        t = [i.strip().strip("'") for i in val2]
        return t[0].lower()
    columns = s.map(unpack_str)
    keys = columns.values
    rec_dtype = np.dtype([(key, 'f8') for key in keys])
    return rec_dtype, keys


def get_div247_dtypes():
    if 'darwin' in sys.platform:
        despath = '/Users/maye/data/diviner/div247/div247.des'
    else:
        despath = '/raid1/u/paige/maye/src/diviner/div247.des'
    return parse_descriptor(despath)


def get_div38_dtypes():
    if 'darwin' in sys.platform:
        despath = '/Users/maye/data/diviner/div38/div38.des'
    else:
        despath = '/u/paige/maye/raid/div38/div38.des'
    return parse_descriptor(despath)

###
### rdrplus tools
###


def read_rdrplus(fpath, nrows):
    with open(fpath) as f:
        line = f.readline()
        headers = parse_header_line(line)

    return pd.io.parsers.read_csv(fpath, names=headers, na_values=['-9999'],
                                      skiprows=1, nrows=nrows)


###
### general tools for data preparation
###


def format_time(intime):
    t = intime.to_datetime()
    s = t.strftime('%Y-%m-%d %H:%M:%S.%f')
    tail = s[-7:]
    f = round(float(tail), 3)
    return pd.Timestamp(s[:-7] + str(f)[1:])


def generate_date_index(dataframe):
    """Parse date fields/columns with pandas date converter parsers.

    Parse the date columns and create a date index from it
    In: pandas dataframe read in from diviner div38 data
    Out: DatetimeIndex
    """
    d = dataframe
    try:
        d.second = np.round(d.second * 1000) / 1000
        date_index = pd.io.date_converters.parse_all_fields(
            d.year, d.month, d.date, d.hour, d.minute, d.second)
    except AttributeError:
        d.ss = np.round(d.ss * 1000) / 1000
        date_index = pd.io.date_converters.parse_all_fields(
            d.yyyy, d.mm, d.dd, d.hh, d.mn, d.ss)
    return date_index


def index_by_time(df, drop_dates=True):
    "must return a new df because the use of drop"
    newdf = df.set_index(generate_date_index(df))
    # force 3-digit precision on time stamp
    # newdf.index = (pd.Series(newdf.index)).map(format_time)
    if drop_dates:
        try:
            cols_to_drop = ['year', 'month', 'date',
                            'hour', 'minute', 'second']
            newdf = newdf.drop(cols_to_drop, axis=1)
        except ValueError:
            cols_to_drop = ['yyyy', 'mm', 'dd', 'hh', 'mn', 'ss']
            newdf = newdf.drop(cols_to_drop, axis=1)
    return newdf


def prepare_data(df_in):
    """Declare NaN value and pad nan data for some."""
    nan = np.nan
    df = index_by_time(df_in)
    df[df == -9999.0] = nan
    df.last_el_cmd.replace(nan, inplace=True)
    df.last_az_cmd.replace(nan, inplace=True)
    df.moving.replace(nan, inplace=True)
    return df


def get_sv_selector(df):
    "Create dataframe selecotr for pointing limits of divconstants 'c' file"
    return (df.last_az_cmd >= c.SV_AZ_MIN) & \
           (df.last_az_cmd <= c.SV_AZ_MAX) & \
           (df.last_el_cmd >= c.SV_EL_MIN) & \
           (df.last_el_cmd <= c.SV_EL_MAX)


def get_bb_selector(df):
    "Create dataframe selecotr for pointing limits of divconstants 'c' file"
    return (df.last_az_cmd >= c.BB_AZ_MIN) & \
           (df.last_az_cmd <= c.BB_AZ_MAX) & \
           (df.last_el_cmd >= c.BB_EL_MIN) & \
           (df.last_el_cmd <= c.BB_EL_MAX)


def get_st_selector(df):
    "Create dataframe selecotr for pointing limits of divconstants 'c' file"
    return (df.last_az_cmd >= c.ST_AZ_MIN) & \
           (df.last_az_cmd <= c.ST_AZ_MAX) & \
           (df.last_el_cmd >= c.ST_EL_MIN) & \
           (df.last_el_cmd <= c.ST_EL_MAX)


def get_stowed_selector(df):
    return (df.last_az_cmd == 0) & (df.last_el_cmd == 0)


def define_sdtype(df):
    df['sdtype'] = 0
    df.sdtype[get_sv_selector(df)] = 1
    df.sdtype[get_bb_selector(df)] = 2
    df.sdtype[get_st_selector(df)] = 3
    df.sdtype[get_stowed_selector(df)] = -2
    # the following defines the sequential list of calibration blocks inside
    # the dataframe. nd.label provides an ID for each sequential part where
    # the given condition is true.
    # this still includes the moving areas, because i want the sv and bbv
    # attached to each other to deal with them later as a separate calibration
    # block
    # DECISION: block labels contain moving data as well
    # WARNING: But not all moving data is contained in block labels!
    # The end of calib block has pointing commands set to nadir.
    # below defined "is_xxx" do NOT contain moving data.
    df['calib_block_labels'] = nd.label((df.sdtype == 1) | \
                                        (df.sdtype == 2) | \
                                        (df.sdtype == 3))[0]
    df['sv_block_labels'] = nd.label(df.sdtype == 1)[0]
    df['bb_block_labels'] = nd.label(df.sdtype == 2)[0]
    df['st_block_labels'] = nd.label(df.sdtype == 3)[0]

    # this resets data from sdtypes >0 above that is still 'moving' to be
    # sdtype=-1 (i.e. 'moving', defined by me)
    df.sdtype[df.moving == 1] = -1

    # now I don't need to check for moving anymore, the sdtypes are clean
    df['is_spaceview'] = (df.sdtype == 1)
    df['is_bbview'] = (df.sdtype == 2)
    df['is_stview'] = (df.sdtype == 3)
    df['is_moving'] = (df.sdtype == -1)
    df['is_stowed'] = (df.sdtype == -2)
    df['is_calib'] = df.is_spaceview | df.is_bbview | df.is_stview

    # this does the same as above labeling, albeit here the blocks are numbered
    # individually. Not sure I will need it but might come in handy.


def fname_to_df(fname, rec_dtype, keys):
    with open(fname) as f:
        data = np.fromfile(f, dtype=rec_dtype)
    df = pd.DataFrame(data, columns=keys)
    return df


def folder_to_df(folder, top_end=None, verbose=False):
    rec_dtype, keys = get_div247_dtypes()
    fnames = glob.glob(folder + '/*.div247')
    fnames.sort()
    if not top_end:
        top_end = len(fnames)
    dfall = pd.DataFrame()
    olddf = None
    for i, fname in enumerate(fnames[:top_end]):
        if verbose:
            print(round(float(i) * 100 / top_end, 1), '%')
        df = fname_to_df(fname, rec_dtype, keys)
        df = prepare_data(df)
        define_sdtype(df)
        if olddf is not None:
            for s in df.filter(regex='_labels'):
                df[s] += olddf[s].max()
        olddf = df.copy()
        dfall = pd.concat([dfall, df])
    to_store = dfall[dfall.calib_block_labels > 0]
    return to_store


def get_storename(folder):
    path = os.path.realpath(folder)
    dirname = '/raid1/maye/data/h5_div247'
    basename = os.path.basename(path)
    storename = os.path.join(dirname, basename + '.h5')
    return storename


def folder_to_store(folder):
    rec_dtype, keys = get_div247_dtypes()
    fnames = glob.glob(folder + '/*.div247')
    if not fnames:
        print("Found no files.")
        return
    fnames.sort()
    # opening store in overwrite-mode
    storename = get_storename(folder)
    print(storename)
    store = pd.HDFStore(storename, mode='w')
    nfiles = len(fnames)
    olddf = None
    cols = ['calib_block_labels', 'sv_block_labels', 'bb_block_labels',
            'st_block_labels', 'is_spaceview', 'is_bbview', 'is_stview',
            'is_moving', 'is_stowed', 'is_calib']
    for i, fname in enumerate(fnames):
        print(round(float(i) * 100 / nfiles, 1), '%')
        df = fname_to_df(fname, rec_dtype, keys)
        df = prepare_data(df)
        define_sdtype(df)
        to_store = df[df.calib_block_labels > 0]
        if len(to_store) == 0:
            continue
        if olddf is not None:
            for s in to_store.filter(regex='_labels'):
                to_store[s] += olddf[s].max()
        olddf = to_store.copy()
        try:
            store.append('df', to_store, data_columns=cols)
        except Exception as e:
            store.close()
            print('at', fname)
            print('something went wrong at appending into store.')
            print(e)
            return
    print("Done.")
    store.close()


class DataPump(object):
    """class to provide Diviner data in different ways."""
    rec_dtype, keys = get_div247_dtypes()
    datapath = '/raid1/maye/data/div247/'

    def __init__(self, fname_pattern=None, timestr=None, fnames_only=False):
        self.fnames_only = fnames_only
        if fname_pattern and os.path.exists(fname_pattern):
            if os.path.isfile(fname_pattern):
                self.get_df(fname_pattern)
            elif os.path.isdir(fname_pattern):
                pass

        self.timestr = timestr
        self.current_time = dateparser(timestr)
        self.fname = os.path.join(datapath,
                                  self.current_time.strftime("%Y%m%d%H"))
        self.increment = timedelta(hours=1)

    #def gen_fnames(self, pattern, top):
    #    for path, dirlist, filelist in os.walk(top)

    def get_fnames(self):
        dirname = os.path.dirname(self.fname)
        fnames = glob.glob(dirname + '/*.div247')
        fnames.sort()
        self.fnames = fnames
        self.index = self.fnames.index(self.fname)

    def open_and_process(self):
        df = fname_to_df(self.fname, self.rec_dtype, self.keys)
        df = prepare_data(df)
        define_sdtype(df)
        self.df = df

    def get_df(self, fname):
        self.fname = fname
        self.get_fnames()
        self.open_and_process()
        return self.df

    def get_next(self):
        self.fname = self.fnames[self.index + 1]
        self.index += 1
        self.open_and_process()
        return self.df


class H5DataPump(object):
    datapath = os.path.join(datapath, 'h5_div247')

    def __init__(self, timestr):
        self.timestr = timestr
        self.fnames = self.get_fnames()
        if len(self.fnames) == 0:
            print("No files found.")
        self.fnames.sort()

    def get_fnames(self):
        return glob.glob(os.path.join(self.datapath, self.timestr[:4] + '*'))

    def store_generator(self):
        for fname in self.fnames:
            yield pd.HDFStore(fname)

    def fname_generator(self):
        for fname in self.fnames:
            yield fname

    def df_generator(self):
        for fname in self.fnames:
            yield self.get_df_from_h5(fname)


class DivXDataPump(object):
    """Abstract Class to stream div38 or div247 data.

    Needs to be completed in derived class.
    Things missing is self.datapath to be set in deriving class.
    """
    timestr_parser = {4: '%Y', 6: '%Y%m',
                      8: '%Y%m%d', 10: '%Y%m%d%H'}

    def __init__(self, timestr):
        """timestr is of format yyyymm[dd[hh]], used directly by glob.

        This means, less files are found if the timestr is longer, as it
        is then more restrictive.
        """
        self.timestr = timestr
        self.time = dt.strptime(timestr,
                                self.timestr_parser[len(timestr)])
        self.fnames = self.find_fnames()
        if len(self.fnames) == 0:
            print("No files found.")
        self.fnames.sort()

    def find_fnames(self):
        "Needs self.datapath to be defined in derived class."
        return glob.glob(os.path.join(self.datapath, self.timestr[:6],
                                      self.timestr + '*'))

    def gen_fnames(self):
        for fname in self.fnames:
            yield fname

    def gen_open(self):
        for fname in self.fnames:
            self.current_fname = fname
            print(fname)
            yield open(fname)

    def get_fname_from_time(self, time):
        return time.strftime("%Y%m%d%H.div247")

    def process_one_file(self, f):
        data = np.fromfile(f, dtype=self.rec_dtype)
        return pd.DataFrame(data, columns=self.keys)

    def gen_dataframes(self, n=None):
        # caller actually doesn't allow n=None anyways. FIX?
        if n == None:
            n = len(self.fnames)
        openfiles = self.gen_open()
        i = 0
        while i < n:
            i += 1
            df = self.process_one_file(openfiles.next())
            yield df

    def clean_final_df(self, df):
        "need to wait until final df before defining sdtypes."
        df = prepare_data(df)
        define_sdtype(df)
        return df

    def get_n_hours(self, n):
        #broken
        print("Broken!!!")
        return
        df = pd.concat(self.gen_dataframes(n))
        return self.clean_final_df(df)

    def get_n_hours_from_t(self, n, t):
        "t in hours, n = how many hours."
        start_time = self.time + timedelta(hours=t)
        l = []
        for i in xrange(n):
            new_time = start_time + timedelta(hours=i)
            basename = self.get_fname_from_time(new_time)
            print(basename)
            dirname = os.path.dirname(self.fnames[0])
            fname = os.path.join(dirname, basename)
            l.append(self.process_one_file(fname))
        df = pd.concat(l)
        return self.clean_final_df(df)

    def read_hour(self, hour):
        pass

    def add_next_hour(self):
        pass

    def get_one_hour(self):
        print("Broken!!")
        return
        for df in self.gen_dataframes():
            yield self.clean_final_df(df)


class RDRDataPump(DivXDataPump):
    datapath = os.path.join(datapath, 'rdr_data')

    def find_fnames(self):
        return glob.glob(os.path.join(self.datapath,
                                      self.timestr + '*_RDR.TAB.zip'))

    def gen_open(self):
        for fname in self.fnames:
            zfile = zipfile.ZipFile(fname)
            yield zfile.open(zfile.namelist()[0])

    def process_one_file(self, f):
        return read_tabbed_rdr(f.name)


class Div247DataPump(DivXDataPump):
    "Class to stream div247 data."
    datapath = os.path.join(datapath, "div247")
    rec_dtype, keys = get_div247_dtypes()


class Div38DataPump(DivXDataPump):
    datapath = os.path.join(datapath, 'div38')
    rec_dtype, keys = get_div38_dtypes()

    def find_fnames(self):
        return glob.glob(os.path.join(self.datapath, self.timestr + '*'))

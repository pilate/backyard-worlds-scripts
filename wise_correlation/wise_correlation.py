import os
import array
import requests
import cStringIO
import index_csv

def convert_floats(radecs):
    return '\n'.join(["%3.10f %+2.10f"%(radec[0],radec[1])
                      for radec in radecs])
def make_post_tbl(radecs):
    # Build IPAC table - fixed width columns:
    # http://irsa.ipac.caltech.edu/applications/DDGEN/Doc/catsearch_table_upload_restrictions.html
    tbl = ["|      ra      |      dec     |\n|    double    |     double   |\n|     deg      |      deg     |\n|     null     |      null    |"]
    for ra,de in radecs:
        tbl.append(" %-14s %-14s"%(ra,de))
    # Return a file-like object so requests's files argument will take it
    c = cStringIO.StringIO('\n'.join(tbl))
    return c
def parse_results(r):
    # Break apart resulting table
    r = r.split('\n')
    last = None
    res = []
    for l in r:
        if len(l) == 0:
            # empty - skip
            continue
        if l[0] in "\\|":
            # Comment or table header - skip
            continue
        # Got a row
        l = l.split() # Split on one-or-more whitespace
        if last is not None and l[0] == last[0]:
            print "Double????"
            print last
            print l
        last = l
        res.append(l)
    return res
def build_and_run_query(radecs):
    c = make_post_tbl(radecs)
    files = {'filename':('WAKKAWAKKA',c)}
    data = {
        "spatial":"Upload",
        "uradius":"30",
        "uradunits":"arcsec",
        "catalog":"allwise_p3as_psd",
        "outfmt":"1",
        "one_to_one":"1",
        "selcols":"w1mpro,w1sigmpro,w1snr,w2mpro,w2sigmpro,w2snr,w3mpro,w3sigmpro,w3snr",
    }
    r = requests.post("http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?",
                      data=data, files=files)
    c.close()
    if r.status_code != 200:
        return r.status_code, r.text
    return r.status_code,parse_results(r.text)

def query_clicks(batch):
    global writelock, irsalock, irsatime, args, indices
    # Build rows
    rows = []
    radecs = []
    f = open(args.file,'rb')
    f.seek(int(batch[0]),os.SEEK_SET)
    for i in xrange(len(batch)):
        # Assume indices are contiguous
        row = f.readline().strip()
        if not row: raise Exception("Ran out of rows in csv")
        rows.append(row)
        row = row.split(',')
        if len(row) < 15:
            raise Exception("Malformed row %s"%(repr(row)))
        radecs.append((row[13],row[14]))
    c, res = build_and_run_query(radecs)
    if c != 200:
        return c, res
    if len(rows) != len(res):
        print "Rowlen and reslen differ"
        print row[0]
        print res[0]
        print row[-1]
        print res[-1]
        print radecs
    for i in xrange(len(rows)):
        rows[i] = "%s,%s,"%(rows[i],','.join(res[i]))
    return c,rows

def work(idxs):
    global writelock, irsalock, irsatime, args, indices
    print "*"*40,'\n',"Running:",idxs,'\n',"*"*40
    batch = indices[idxs[0]:idxs[1]]
    try:
        stat,data = query_clicks(batch)
    except requests.exceptions.ConnectionError,e:
        idxs1 = (idxs[0],idxs[0]+((idxs[1]-idxs[0])/2))
        idxs2 = (idxs[0]+((idxs[1]-idxs[0])/2),idxs[1])
        print idxs,"broke. Splitting it in half and running again:",idxs1,idxs2
        work(idxs1)
        work(idxs2)
        return
    if stat != 200:
        print "Error:",data
        return
    writelock.acquire()
    of = open(args.outfile,'ab')
    for row in data:
        of.write(row)
        of.write('\n')
    of.close()
    writelock.release()

def winit(writelock_, irsalock_, irsatime_, args_, indices_):
    global writelock, irsalock, irsatime, args, indices
    writelock = writelock_
    irsalock = irsalock_
    irsatime = irsatime_
    args = args_
    indices = indices_

def main():
    import os
    import argparse
    import multiprocessing
    # Do args & usage
    ap = argparse.ArgumentParser(description="Enrich click data with WISE fields. "+
                                 "Takes click data as CSV file")
    ap.add_argument("file",type=str,
                    help="Path to CSV file with click data")
    ap.add_argument("--idxfile",type=str,default="",
                    help="Input indexs to csv file.")
    ap.add_argument("--outfile",type=str,required=False,
                    help="Where to write results")
    ap.add_argument("--batchsize",type=int,default=8192)
    ap.add_argument("--maxprocs",type=int,default=8)
    ap.add_argument("--skipto",type=int,default=0,
                    help="Skip to line in csv. Does not treat header separately")
    ap.add_argument("--runto",type=int,default=None)
    args = ap.parse_args()
    # Validate / finalize args
    if args.outfile == "" or args.outfile is None:
        b,e = os.path.splitext(args.file)
        args.outfile = "%s_processed.csv"%(b)
    open(args.outfile,'wb').close() # test file and truncate
    # Divide input into batches
    # First, build indexes into the CSV file
    if args.idxfile != "":
        indices = index_csv.load_indices(args.idxfile)
    else:
        indices = index_csv.index_csv(args.file)
    if args.runto is None:
        args.runto = len(indices)
    assert(args.skipto < args.runto)
    # Then, coordinate batching.
    batches = [(i,min(i+args.batchsize,args.runto))
               for i in xrange(args.skipto,args.runto,args.batchsize)]
    # Create locks
    # Controls write access to csv output file
    writelock = multiprocessing.Lock()
    # Throttles connections to Irsa
    irsalock = multiprocessing.Lock()
    irsatime = 0
    # Create workers
    p = multiprocessing.Pool(args.maxprocs,initializer=winit,
                             initargs=(writelock, irsalock,
                                       irsatime, args, indices))
    p.map(work,batches)
    #winit(writelock, irsalock, irsatime, args, indices)
    #work(batches[0])
    
if __name__ == "__main__":
    main()

"""
JOIN(BD,Subject) CSV format reader
ra,de are the ra,de of the BD
"""
import collections

BDSubjectHeader = "subject_id,ra,de"
BDSubject = collections.namedtuple("BDSubject",BDSubjectHeader)

class BDSubjectReader:
    """""" 
    def __init__(self,fname):
        self.fname = fname
        self.f = open(self.fname,'rb')
        # Skip header
        l = self.f.readline()
        if l.strip() != BDSubjectHeader:
            raise Exception("%s is not in %s format"%(self.fname,
                                                      self.__class__.__name__))

    def readline(self):
        l = self.f.readline()
        if not l:
            return None
        return BDSubject(*l.strip().split(','))

    def __iter__(self):
        while True:
            o = self.readline()
            if not o: raise StopIteration
            yield o
            
def main():
    import sys
    print "Testing BDSubject"
    rdr = BDSubjectReader(sys.argv[1])
    for i in xrange(10):
        r = rdr.readline()
        print r

if __name__ == "__main__":
    main()
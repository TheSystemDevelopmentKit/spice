"""
VACASK rawfile read from:

https://codeberg.org/arpadbuermen/VACASK/src/branch/main/python/src/vacask/rawfile.py

at commit da17a594f9a67bd660bc68664be1a4bdb480a353

"""
import numpy as np

__all__ = [ 'rawread' ]

BSIZE_SP = 512 # Max size of a line of data
headerEntryNames = set([
	b'title', b'date', b'plotname', b'flags', b'no. variables',
	b'no. points', b'dimensions', b'command', b'option'
])

class RawFile:
	def __init__(self, header, data, sweeps=0):
		self.title = header['title'].decode('ascii')
		self.date = header['date'].decode('ascii')
		self.plotname = header['plotname'].decode('ascii')
		self.flags = header['flags'].decode('ascii')
		self.names = header['varnames']
		self.data = data
		ndata, nvars = data.shape

		# Build name index
		self.nameToIndex = { self.names[ii]: ii for ii in range(nvars) }

		# Split sweeps, if sweeps is a string, all vectors before the one named sweeps are sweep scales
		if isinstance(sweeps, str):
			# Find vector with name sweeps
			sweeps = self.names.index(sweeps)

		self.sweeps = sweeps
		if sweeps>0:
			allends = np.array([], dtype='int64')
			for ii in range(sweeps):
				# ii-th outermost sweep
				var = data[:,ii]
				ends = (np.where(var[1:]!=var[:-1])[0]+1)
				ends=np.append(ends, ndata)
				allends = np.append(allends, ends)

			# Drop duplicates from array
			self.allends = np.unique(allends)

			# Sort
			self.allends.sort()

			# Beginnings
			self.allbegins = np.hstack([0, self.allends[:-1]])

			# Sweep groups
			self.sweepGroups = self.allbegins.size
		else:
			self.allbegins = np.array([0], dtype='int64')
			self.allends = np.array([ndata], dtype='int64')
			self.sweepGroups = 1

	def __getitem__(self, key):
		if type(key) is tuple:
			# (sweepGroup, vector)
			sweepGroup, vec = key
			ii1 = self.allbegins[sweepGroup]
			ii2 = self.allends[sweepGroup]
		else:
			# vector
			# Return all points of all sweeps
			ii1 = 0
			ii2 = self.data.shape[0]
			vec = key

		# resolve vector, if needed
		if type(vec) is str:
			vec = self.nameToIndex[vec]

		return self.data[ii1:ii2,vec]

	def sweepData(self, sweepGroup):
		ii = self.allbegins[sweepGroup]
		data = {}
		for jj in range(self.sweeps):
			data[self.names[jj]] = self.data[ii,jj]
		return data


class RawData:
	def __init__(self, arrs):
		self.arrs = arrs

	def get(self, ndx=0, sweeps=0):
		plot, arr = self.arrs[ndx]
		return RawFile(plot, arr, sweeps)


def rawread(fname):
	# Example header of raw file
	# Title: rc band pass example circuit
	# Date: Sun Feb 21 11:29:14  2016
	# Plotname: AC Analysis
	# Flags: complex
	# No. Variables: 3
	# No. Points: 41
	# Variables:
	#         0       frequency       frequency       grid=3
	#         1       v(out)  voltage
	#         2       v(in)   voltage
	# Binary:
	with open(fname, 'rb') as fp:
		plot = {}
		count = 0
		arrs = []
		while (True):
			try:
				splitLine = fp.readline(BSIZE_SP).split(b':', maxsplit=1)
			except OSError as e:
				raise RuntimeError("Failed to read a line from file.") from e
			if len(splitLine) == 2:
				# Ordinary header entries
				if splitLine[0].lower() in headerEntryNames:
					plot[splitLine[0].lower().decode('ascii')] = splitLine[1].strip()
				# Variable list
				if splitLine[0].lower() == b'variables':
					nvars = int(plot['no. variables'])
					npoints = int(plot['no. points'])
					plot['no. variables'] = nvars
					plot['no. points'] = npoints
					plot['varnames'] = []
					plot['varunits'] = []
					for ii in range(nvars):
						# Get variable description, split it at spaces
						txt = fp.readline(BSIZE_SP).strip().decode('ascii')
						varDesc = txt.split(maxsplit=3)
						if (len(varDesc)>3 and 'dims' in varDesc[3]):
							raise NotImplementedError("Raw files with different length vectors are not supported.")
						# Check variable numbering
						assert(ii == int(varDesc[0]))
						# Get name and units
						plot['varnames'].append(varDesc[1])
						plot['varunits'].append(varDesc[2])
						# TODO: get extra data like dims
				# Binary data start
				if splitLine[0].lower() == b'binary':
					# Check for unpadded
					if b'unpadded' in plot['flags']:
						raise NotImplementedError("Unpadded raw files are not supported.")
					arr = np.fromfile(
						fp,
						dtype=np.complex128 if b'complex' in plot['flags'] else np.float64,
						count=npoints*nvars
					).reshape((npoints, nvars))
					arrs.append((plot, arr))
				if splitLine[0].lower() == b'ascii':
					raise NotImplementedError("ASCII files are not supported.")
			else:
				# Header line does not have two parts, we reached the end
				break
	return RawData(arrs)


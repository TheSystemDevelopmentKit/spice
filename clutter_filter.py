import numpy as np
#Test data
start=0.1
a=np.array([[0, 1], [ 0.1, 2], [0.101, 3], [0.2, 4], [0.201, 5], [0.3, 6]],dtype=float)
a[:,0] += start
step=0.1

#relative tolerable error in the timestep. Values outside of this rage will be discarded.

relerr=1e-6 #percent of the step
stepvec=start+np.arange(0,a.shape[0]).reshape(1,-1)*step
steplow=(stepvec-relerr*step).reshape(-1,1)
stephigh=(stepvec+relerr*step).reshape(-1,1)
stepspec=np.r_['1',steplow,stephigh]
#b=filter(lambda val: val > stepvec[0,0] and val < stepvec[0,1], a) 
#
def cond(test,val):
    if val >= test[0] and val <= test[1]:
        return True
    else: 
        return False

#This loops through the values of A only once.
rowselect=[ False for x in range(a.shape[0])]
selectorindex=0
for index in range(a.shape[0]):
    if stepspec[selectorindex,0] < a[index,0] < stepspec[selectorindex,1]:
        rowselect[index]=True
        selectorindex += 1

#np.compress(bool vector satisfying stepspec.a,axis=0)
b=np.compress(rowselect,a,axis=0)

print(a)
print(b)




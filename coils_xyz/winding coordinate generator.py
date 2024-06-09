import numpy as np
import matplotlib.pyplot as plt
'''Code to work with coil coordinates and prepare geometries for import into Fusion 360.
Fusion 360 uses cm as unit for all geometry definitions, therefore after importing 
########  ALL COORDINATES IN THIS CODE USES CM AS UNIT!?!!!!!!!!!##########################################
'''
#Fusion units:
Fcm = 1
Fm = 100
Fmm = 0.1

def generate_filenames(base_filename, N):
    # Extract the prefix  assumin suffix is .txt
    prefix = base_filename.rstrip('.txt')
    prefix = prefix.rstrip('0123456789')
    suffix = '.txt'

    # Generate the list of filenames
    filenames = []
    for i in range(N):
        filenames.append(f"{prefix}{i}{suffix}")

    return filenames
def loadAndScale(filename, coilNumber, scalingfactor=1):
    '''
    load and scale coordinates of a set of coils
    :param filename: filename of one of the coils, extension must be '.txt', files must be numbered starting at 0 up to coilNumber-1
    :param coilNumber: number of coils in the set
    :param scalingfactor: real factor to scale the design by. Scaling from m to cm is done automatically
    :return: list coilNumber numpy arrays with shape of 3 by X, containing the xyz coordinates.
    '''
    filenameList = generate_filenames(filename, coilNumber)
    coilCoordList = []
    for thisfilename in filenameList:
        data = np.loadtxt(thisfilename, delimiter=' ')
        datashape = np.shape(data)
        if datashape[1] != 3:
            raise Exception('Data in file ' + thisfilename + ' has wrong shape')
        data = np.asarray(data) * 100 * scalingfactor  # convert to cm and scale
        coilCoordList.append(data)
    return coilCoordList

def coilCG(coilCoordList):
    '''
    calculates center of gravity for each coil in the list
    :param coilCoordList: list of numpy arrays containing xyz coil coordinates
    :return: list of CGs of each coil. Contains xyz numpy vectors with 3 components.
    '''
    CGlist = []
    for xyzCoord in coilCoordList:
        CGlist.append(np.mean(xyzCoord, axis=0))
    return CGlist

def CGvectors(CGlist):
    '''
    calculates vectors that give a axis direction for each coil, computed by the connection between CGs of previous and next coil. normalized.
    :param CGlist: list of the CGs of all coils, MUST BE ORDERED correctly
    :return: list of axis vectors, normalized. List contains xyz numpy vectors with 3 components.
    '''
    N = len(CGlist)
    CGvectorList = []
    if N < 3:
        raise Exception('Too few coils loaded (<3) to compute CG vectors')
    for i in range(N):
        if i == 0:
            CGvector = CGlist[1]-CGlist[N-1]
        elif i == N-1:
            CGvector = CGlist[0] - CGlist[N - 2]
        else:
            CGvector = CGlist[i+1] - CGlist[i - 1]
        CGvector /= np.linalg.norm(CGvector) #normalize CGvector
        CGvectorList.append(CGvector)
    return CGvectorList

def CGorientedRails(coilCoordList, railScale=0.9):
    '''
    create rails for sweeping command, so that the inside of the sweeped geometry always faces the CG of each coil
    :param coilCoordList: list of numpy arrays containing xyz coil coordinates
    :param railScale: scaling factor defines how far inside of the coil the rail will be, typ. < 1 but not too small (>
        0.8 depending on the smalles radius of the coil in order to avoid overlaps)
    :return: list of numpy arrays containing xyz rail coordinates. Shaped like coilCoordList
    '''
    CGlist = coilCG(coilCoordList)
    railList = []
    for i, xyzCoord in enumerate(coilCoordList):
        CG = CGlist[i]
        x = xyzCoord[:, 0]
        y = xyzCoord[:, 1]
        z = xyzCoord[:, 2]
        xyzCoord[:, 0] = (x - CG[0]) * railScale + CG[0]
        xyzCoord[:, 1] = (y - CG[1]) * railScale + CG[1]
        xyzCoord[:, 2] = (z - CG[2]) * railScale + CG[2]
        railList.append(xyzCoord)
    return railList

def parallelOrientedRails(coilCoordList, railDistance=1):
    '''
    creates rails that are the original coil coordinates offset in the direction between previous and next coil CG
    :param coilCoordList: list of numpy arrays containing xyz coil coordinates
    :param railDistance: offset distance in cm
    :return: list of numpy arrays containing xyz rail coordinates. Shaped like coilCoordList
    '''
    CGlist = coilCG(coilCoordList)
    CGvectorList = CGvectors(CGlist)
    railList = []
    for i, xyzCoord in enumerate(coilCoordList):
        CG = CGlist[i]
        CGvector = CGvectorList[i] #vector between next and previous CG as approximation of B direction in this coils CG
        Npoints = len(xyzCoord[:,0])
        railList.append(xyzCoord + np.tile(CGvector*railDistance, (Npoints,1)))
    return railList

def pancakesParallelOriented(coilCoordList, Nturns, turnThickness, torOffset):
    '''
    function to generate a spiral that fits inside a parallel oriented structure.
    :param coilCoordList: list of numpy arrays containing xyz coil coordinates
    :param Nturns: Number of turns of the spiral, must be integer
    :param turnThickness: distance in cm how much tighter each turn is wound (~radius difference). neg and pos values
        change the winding direction (inside to outside / outside to inside). The direction (clockwise / CCW) is defined
         by how the coilCoordList is stored.
    :param torOffset: offset in the B-field direction in cm
    :return: list of numpy arrays containing xyz pancake (spiral) coordinates. Shaped like coilCoordList
    '''
    CGlist = coilCG(coilCoordList)
    CGvectorList = CGvectors(CGlist)
    pancakeList = []
    for i, xyzCoord in enumerate(coilCoordList):
        CG = CGlist[i]
        CGvector = CGvectorList[i] #vector between next and previous CG as approximation of B direction in this coils CG
        Npoints = len(xyzCoord[:, 0])
        radOffset= np.linspace(0.5*turnThickness*Nturns,-0.5**turnThickness*Nturns,Npoints*Nturns)
        xyzPancake = np.zeros((Npoints*Nturns,3))
        for j in range(Npoints*Nturns):
            j_coil = np.mod(j,Npoints)
            PtoCG = CG - xyzCoord[j_coil,:] # vector from this coil point to CG
            radVector = PtoCG - CGvector * (np.sum(PtoCG*CGvector)) #substract the component parrallel to CG vector from PtoCG
            radVector = radVector/np.sqrt(np.sum(radVector**2)) #normalize radVector
            #something like vector point to CG - CGvector times dot product of this vector time CGvector and all of that normalized.
            xyzPancake[j, :] = xyzCoord[j_coil,:] + radOffset[j] * radVector + torOffset * CGvector
        pancakeList.append(xyzPancake)
    return pancakeList

def listTotxt(filename, list):
    '''
    saves the coordinates that are content of the list to be later imported by fusion script
    :param filename: basis filename (and directory), extension must be .txt or none
    :param list: list of numpy arrays containing xyz coordinates (shape Nx3)
    :return: none, saves txts directly
    '''
    N = len(list)
    filenames = generate_filenames(filename, N)
    for i in range(N):
        np.savetxt(filenames[i], list[i], delimiter=' ')

def closeLoop(xyz):
    '''
    Closes the geometry to a loop by repeating the first points coordinates at the end.
    :param xyz: xyz coordinates or list of numpy arrays containing xyz coordinates (shape Nx3)
    :return: xyz but with the first points coordinates repeated at the end
    '''
    #code something that decides if its a list or a ndarray and act accordingly.
    #or something that works on both
    raise Exception('closeLoop not implemeted yet')

if __name__ == "__main__":
    print('hi, how are you dooin?')
    coilCoordlist = loadAndScale('coilData\coil_coordinates0.txt', 12, 0.33)
    pancakeCoordList = pancakesParallelOriented(coilCoordlist, 6, 8*Fmm, 2.5*8*Fmm)
    railCoorrdList = parallelOrientedRails(coilCoordlist)
    if False: #3D Plot
        ax = plt.figure().add_subplot(projection='3d')
        for i in range(12):
            panCk = pancakeCoordList[i]
            cl = coilCoordlist[i]
            ax.plot(panCk[:,0], panCk[:,1], panCk[:,2], label='pancake')
            ax.plot(cl[:, 0], cl[:, 1], cl[:, 2], label='coil')
            CGlist = coilCG(coilCoordlist)
            CG = CGlist[i]
            vecList = CGvectors(CGlist)
            vec = vecList[i] * 20
            ax.plot([CG[0], CG[0]+vec[0]], [CG[1], CG[1]+vec[1]],[CG[2], CG[2]+vec[2]], label='CG vector'+str(i))
            ax.plot(CG[0], CG[1], CG[2],'.', label='CG '+str(i))
        ax.legend()
        plt.show()
    if True: #save csv
        np.savetxt('exportData\pancakeTest.csv', pancakeCoordList[0], delimiter=',')
        np.savetxt('exportData\coilTest.csv', coilCoordlist[0], delimiter=',')
        np.savetxt('exportData\RailParallelTest.csv', railCoorrdList[0], delimiter=',')
    if False: #save all txt
        listTotxt('exportData\pancake0.txt', pancakeCoordList)
        listTotxt('exportData\coil0.txt', coilCoordlist)

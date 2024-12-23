# -*- coding: utf-8 -*-
"""p1_cifar.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1m6-CJ8oER7Y1evG2vZHTs5XyjJ1TEBnf
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from sklearn.datasets import load_iris
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score
from sklearn.decomposition import PCA
from sklearn.svm import SVC
from sklearn import preprocessing
from keras.datasets import cifar10
import cv2

"""## GIST"""

# This class implements the extraction of a GIST descriptor from an image.
# The GIST descriptor was originally proposed in https://people.csail.mit.edu/torralba/code/spatialenvelope/
# This code was taken from https://github.com/imoken1122/GIST-feature-extractor, on september 2020

import numpy as np
import numpy.matlib as nm
import numpy.fft as f
from PIL import Image

class GIST():
    def __init__(self,param):
        self.param = param

    def _createGabor(self,orr,n):

        gabor_param = []
        Nscalse = len(orr)
        Nfilters = sum(orr)
        if len(n) == 1:
            n = [n[0],n[0]]
        for i in range(Nscalse):
            for j in range(orr[i]):
                gabor_param.append([.35,.3/(1.85**(i)),16*orr[i]**2/32**2, np.pi/(orr[i])*(j)])
        gabor_param = np.array(gabor_param)
        fx, fy = np.meshgrid(np.arange(-n[1]/2,n[1]/2-1 + 1), np.arange(-n[0]/2, n[0]/2-1 + 1))
        fr = f.fftshift(np.sqrt(fx**2+fy**2))
        t = f.fftshift(np.angle(fx+ 1j*fy))

        G = np.zeros([n[0],n[1],Nfilters])
        for i in range(Nfilters):
            tr = t + gabor_param[i,3]
            tr+= 2*np.pi*(tr < -np.pi) - 2 * np.pi*(tr>np.pi)
            G[:,:,i] = np.exp(-10*gabor_param[i,0]*(fr/n[1]/gabor_param[i,1]-1)**2-2*gabor_param[i,2]*np.pi*tr**2)

        return G

    def _more_config(self,img):

        self.param["imageSize"] = [img.shape[0], img.shape[1]]
        self.param["G"] = self._createGabor(self.param["orientationsPerScale"],np.array(self.param["imageSize"])+2*self.param["boundaryExtension"])


    def _preprocess(self,img):
        M = self.param["imageSize"]
        if len(M) == 1:
            M = [M, M]
        scale = np.max([M[0]/img.shape[0], M[1]/img.shape[1]])
        newsize = list(map(int,np.round(np.array([img.shape[1],img.shape[0]]) * scale)))
        img = np.array(Image.fromarray(img).resize(newsize, Image.BILINEAR))
        #img = imresize(img,newsize,'bilinear')

        nr,nc = img.shape
        sr = (nr-M[0])/2
        sc = (nc-M[1])/2

        img = img[int(sr):int(sr+M[0])+ 1,int(sc):int(sc+M[1])+1]
        img = img- np.min(img)
        if np.sum(img) != 0:
            img = 255*(img/np.max(img))

        return img


    def _prefilt(self,img):

        w = 5
        fc=self.param["fc_prefilt"]
        s1 = fc/np.sqrt(np.log(2))
        img=np.log(img +1 )
        img = np.pad(img,[w,w],"symmetric")

        sn,sm = img.shape
        n = np.max([sn,sm])
        n += n%2

        if sn == sm:
            img = np.pad(img,[0,int(n-sn)],"symmetric")
        else:
            img = np.pad(img,[0,int(n-sn)], "symmetric")[:,:sm]

        fx,fy = np.meshgrid(np.arange(-n/2,n/2-1 + 1),np.arange(-n/2,n/2-1 + 1))
        gf = f.fftshift((np.exp(-(fx**2+fy**2)/(s1**2))))
        gf = nm.repmat(gf,1,1)
        output = img - np.real(f.ifft2(f.fft2(img)*gf))

        localstd = nm.repmat(np.sqrt(abs(f.ifft2(f.fft2(output**2)*gf))), 1 ,1 )
        output = output/(0.2+localstd)
        output = output[w:sn-w, w:sm-w]
        return output

    def _gistGabor(self,img):

        w = self.param["numberBlocks"]
        G = self.param["G"]
        be = self.param["boundaryExtension"]
        ny,nx,Nfilters = G.shape
        W = w[0] * w[1]
        N = 1
        g = np.zeros((W*Nfilters, N))
        img = np.pad(img,[be,be],"symmetric")
        img = f.fft2(img)

        k = 0
        for n in range(Nfilters):
            ig = abs(f.ifft2(img*nm.repmat(G[:,:,n],1,1)))
            ig = ig[be:ny-be,be:nx-be]
            v = self._downN(ig,w)
            g[k:k+W,0] = v.reshape([W,N],order = "F").flatten()
            k += W
        return np.array(g)

    def _downN(self,x,N):
        nx = list(map(int,np.floor(np.linspace(0,x.shape[0],N[0]+1))))
        ny = list(map(int,np.floor(np.linspace(0,x.shape[1],N[1]+1))))
        y  = np.zeros((N[0],N[1]))
        for xx in range(N[0]):
            for yy in range(N[1]):
                a = x[nx[xx]:nx[xx+1], ny[yy]:ny[yy+1]]
                v = np.mean(np.mean(a,0))
                y[xx,yy]=v
        return y

    def _gist_extract(self,img):

        self._more_config(img)

        img = self._preprocess(img)

        output = self._prefilt(img)

        gist = self._gistGabor(output)

        return gist.flatten()

# get training data
(im_train_and_val, y_train_and_val), (im_test, y_test) = cifar10.load_data()
print('Training set size: {}'.format(im_train_and_val.shape))
print('Training set size: {}'.format(im_test.shape))

# Parameters needed for the GIST descriptor
param = {
        "orientationsPerScale":np.array([8,8]),
         "numberBlocks":[4,4],
        "fc_prefilt":10,
        "boundaryExtension":32
}

# Extract the GIST descriptor of image 134
mygist = GIST(param)
imggray = cv2.cvtColor(im_train_and_val[134,:,:,:], cv2.COLOR_BGR2GRAY)
plt.imshow(im_train_and_val[134,:,:,:])
plt.show()
gistdesc = np.squeeze(mygist._gist_extract(imggray))
print('GIST descriptor: {}'.format(gistdesc.shape))

# Parameters needed for the GIST descriptor
exit()
param = {
        "orientationsPerScale":np.array([8,8]),
         "numberBlocks":[4,4],
        "fc_prefilt":10,
        "boundaryExtension":32
}

# Extract GIST descriptor of every image in the dataset
mygist = GIST(param)

n_train_and_val = im_train_and_val.shape[0]
n_test = im_test.shape[0]
x_train_and_val_gist = np.zeros((n_train_and_val,256))
x_test_gist = np.zeros((n_test,256))

for i in range(n_train_and_val):
  imggray = cv2.cvtColor(im_train_and_val[i,:,:,:], cv2.COLOR_BGR2GRAY)
  x_train_and_val_gist[i,:] = np.squeeze(mygist._gist_extract(imggray))
  print('Converting training set, image ', i, ' out of ', n_train_and_val)

for i in range(n_test):
  imggray = cv2.cvtColor(im_test[i,:,:,:], cv2.COLOR_BGR2GRAY)
  x_test_gist[i,:] = np.squeeze(mygist._gist_extract(imggray))
  print('Converting test set, image ', i, ' out of ', n_test)

"""##2.1 Split data"""

(im_train_and_val, y_train_and_val), (im_test, y_test) = cifar10.load_data()

np.random.seed(42)

# Unir el conjunto de datos de entrenamiento y prueba para dividir todo nuevamente
images = np.concatenate((im_train_and_val, im_test), axis=0)
labels = np.concatenate((y_train_and_val, y_test), axis=0)

# Definir el tamaño del conjunto
n_total = images.shape[0]
n_train = int(n_total * 0.80)  # 80% para entrenamiento
n_val = int(n_total * 0.10)    # 10% para validación
n_test = n_total - n_train - n_val

# Mezclar los datos de forma aleatoria
indices = np.random.permutation(n_total)
train_idx, val_idx, test_idx = indices[:n_train], indices[n_train:n_train+n_val], indices[n_train+n_val:]

# Crear los conjuntos de entrenamiento, validación y prueba
x_train, y_train = images[train_idx], labels[train_idx]
x_val, y_val = images[val_idx], labels[val_idx]
x_test, y_test = images[test_idx], labels[test_idx]

# Mostrar algunas imágenes del conjunto de entrenamiento
fig, axes = plt.subplots(1, 5, figsize=(15,3))
for i, ax in enumerate(axes):
    ax.imshow(x_train[i])
    ax.set_title(f'Label: {y_train[i][0]}')
    ax.axis('off')
plt.show()

# Mostrar el tamaño de cada conjunto
print(f'Tamaño del conjunto de entrenamiento: {x_train.shape}')
print(f'Tamaño del conjunto de validación: {x_val.shape}')
print(f'Tamaño del conjunto de prueba: {x_test.shape}')

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import numpy as np

# Aplanar las imágenes de 32x32x3
x_train_flat = x_train.reshape(x_train.shape[0], -1)
x_val_flat = x_val.reshape(x_val.shape[0], -1)
x_test_flat = x_test.reshape(x_test.shape[0], -1)

# Normalizar los datos (escalar los valores de píxeles de 0-255 a un rango de 0-1)
scaler = StandardScaler()
x_train_flat_scaled = scaler.fit_transform(x_train_flat)
x_val_flat_scaled = scaler.transform(x_val_flat)
x_test_flat_scaled = scaler.transform(x_test_flat)

# Aplicar PCA
# Según cantidad de varianza explicada (95%)
pca = PCA(n_components=0.95)
x_train_pca = pca.fit_transform(x_train_flat_scaled)
x_val_pca = pca.transform(x_val_flat_scaled)
x_test_pca = pca.transform(x_test_flat_scaled)

# Mostrar la cantidad de componentes principales seleccionados
print(f"Componentes principales seleccionados: {pca.n_components_}")

y_train = y_train.ravel()
y_val = y_val.ravel()
y_test = y_test.ravel()

print(f'Tamaño del conjunto de validación: {x_train_flat.shape}')
print(f'Tamaño del conjunto de entrenamiento: {x_train_pca.shape}')
print(f'Tamaño del Test de prueba: {y_train.shape}')

"""### 2.1.1 Clasificación imágenes"""

from sklearn.metrics import accuracy_score, confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt

def plot_confusion_matrix(y_val, y_val_pred, title):
  conf_matrix = confusion_matrix(y_val, y_val_pred)
  plt.figure(figsize=(8,6))
  sns.heatmap(conf_matrix, annot=True, fmt="d", cmap="Blues", xticklabels=np.unique(y_val), yticklabels=np.unique(y_val))
  plt.title(f'Matriz de Confusión - {title}')
  plt.ylabel('Etiqueta verdadera')
  plt.xlabel('Etiqueta predicha')
  plt.show()

def train_model(model, title, x_train, y_train, x_val, y_val):
  model.fit(x_train, y_train)
  y_val_pred = model.predict(x_val)

  # Evaluar la precisión en el conjunto de validación
  val_acc = accuracy_score(y_val, y_val_pred)
  print(f'Precisión en validación ({title}): {val_acc:.4f}')
  plot_confusion_matrix(y_val, y_val_pred, title)
  return val_acc

from sklearn.linear_model import LogisticRegression

# Crear el modelo de regresión logística
log_reg = LogisticRegression(max_iter=500, solver='lbfgs')
train_model(log_reg, 'Logistic Regression', x_train_pca, y_train, x_val_pca, y_val)

from sklearn.neighbors import KNeighborsClassifier

knn_model = KNeighborsClassifier(n_neighbors=1)
train_model(knn_model, 'KNN', x_train_pca, y_train, x_val_pca, y_val)

from sklearn.svm import SVC

# Crear el modelo SVM
svm_model = SVC(kernel='linear')
train_model(svm_model, 'SVM', x_train_pca, y_train, x_val_pca, y_val)



"""## 2.2 Clasificación usando GIST"""

(im_train_and_val, y_train_and_val), (im_test, y_test) = cifar10.load_data()

np.random.seed(42)

# Unir el conjunto de datos de entrenamiento y prueba para dividir todo nuevamente
images = np.concatenate((im_train_and_val, im_test), axis=0)
labels = np.concatenate((y_train_and_val, y_test), axis=0)

# Definir el tamaño del conjunto
n_total = images.shape[0]
n_train = int(n_total * 0.80)  # 80% para entrenamiento
n_val = int(n_total * 0.10)    # 10% para validación
n_test = n_total - n_train - n_val

# Mezclar los datos de forma aleatoria
indices = np.random.permutation(n_total)
train_idx, val_idx, test_idx = indices[:n_train], indices[n_train:n_train+n_val], indices[n_train+n_val:]

# Crear los conjuntos de entrenamiento, validación y prueba
x_train, y_train = images[train_idx], labels[train_idx]
x_val, y_val = images[val_idx], labels[val_idx]
x_test, y_test = images[test_idx], labels[test_idx]

# Mostrar algunas imágenes del conjunto de entrenamiento
fig, axes = plt.subplots(1, 5, figsize=(15,3))
for i, ax in enumerate(axes):
    ax.imshow(x_train[i])
    ax.set_title(f'Label: {y_train[i][0]}')
    ax.axis('off')
plt.show()

# Mostrar el tamaño de cada conjunto
print(f'Tamaño del conjunto de entrenamiento: {x_train.shape}')
print(f'Tamaño del conjunto de validación: {x_val.shape}')
print(f'Tamaño del conjunto de prueba: {x_test.shape}')

from tqdm import tqdm
x_train_gist = np.zeros((x_train.shape[0], 256))
x_val_gist = np.zeros((x_val.shape[0], 256))
x_test_gist = np.zeros((x_test.shape[0], 256))

# Instanciar el objeto GIST con los parámetros dados
mygist = GIST(param)

# Extraer descriptores GIST del conjunto de entrenamiento con barra de progreso
for i in tqdm(range(x_train.shape[0]), desc="Extrayendo GIST del conjunto de entrenamiento"):
    imggray = cv2.cvtColor(x_train[i, :, :, :], cv2.COLOR_BGR2GRAY)
    x_train_gist[i, :] = np.squeeze(mygist._gist_extract(imggray))

# Extraer descriptores GIST del conjunto de validación con barra de progreso
for i in tqdm(range(x_val.shape[0]), desc="Extrayendo GIST del conjunto de validación"):
    imggray = cv2.cvtColor(x_val[i, :, :, :], cv2.COLOR_BGR2GRAY)
    x_val_gist[i, :] = np.squeeze(mygist._gist_extract(imggray))

# Extraer descriptores GIST del conjunto de prueba con barra de progreso
for i in tqdm(range(x_test.shape[0]), desc="Extrayendo GIST del conjunto de prueba"):
    imggray = cv2.cvtColor(x_test[i, :, :, :], cv2.COLOR_BGR2GRAY)
    x_test_gist[i, :] = np.squeeze(mygist._gist_extract(imggray))


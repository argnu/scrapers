# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from os import path
from pymongo import MongoClient
import sys
import requests
import urllib2
import urllib
import warnings
import socket
warnings.filterwarnings('ignore')

client = MongoClient('localhost', 27017)
db = client['dominiopublico']
urlPrincipal = "http://www.dominiopublico.es/"


#Código para descargar archivo con barra de progreso
def download_file(url, nombre):
    file_name = "/media/datos/Liberascio/ServidorContenidoLibre/Libros/dominiopublico.es/" + nombre
    if (not path.isfile(file_name)):
        try:
            u = urllib2.urlopen(url, timeout=5)
            f = open(file_name, 'wb')
            meta = u.info()
            file_size = int(meta.getheaders("Content-Length")[0])
            print "Descargando archivo: %s Bytes: %s" % (file_name, file_size)

            file_size_dl = 0
            block_sz = 8192
            while True:
                buffer = u.read(block_sz)
                if not buffer:
                    break

                file_size_dl += len(buffer)
                f.write(buffer)
                status = r"%10d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100. / file_size)
                status = status + chr(8)*(len(status)+1)
                print status,

            print "\n"
            f.close()
            return True
        except urllib2.URLError, e:
            print "There was an error: %r" % e
            return False
        except socket.timeout:
            print "Timeout!"
            return False
    return True


def getAutores(html):
    autores = []
    tdItems = html.find_all('td', {'class': 'mna'})
    for td in tdItems:
        a = td.find('a')
        if 'autor.php?compuesto=' in a.get('href'):
            compuesto = urllib2.unquote(a.get('href').split('?')[1][10:])
            comSplit = compuesto.split(',')
            apellido = comSplit[0]
            autor = {
                'url': urlPrincipal + a.get('href'),
                'apellido': apellido,
            }
            if (len(comSplit)>1):
                autor['nombre'] = comSplit[1]
            autores.append(autor)
    return autores


def getInfoAutor(url):
    libros = []
    r = requests.get(url)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text)
        nombre = soup.find('h2').text
        aItems = soup.find_all('a')
        for a in aItems:
            if 'Descarga' in a.text:
                url = a.get('href')
                extension = url.split('.')[-1]
                if (extension in ['pdf', 'epub', 'doc', 'odt']):
                    if a.get('download'):
                        datos = a.get('download').split('-')
                        fileName = a.get('download')
                        titulo = datos[1].split('.')[0]
                    else:
                        if '-' in url.split('/')[-1]:
                            datos = url.split('/')[-1].split('-')
                            titulo = datos[1].split('.')[0]
                        else:
                            titulo = url.split('/')[-1]
                        fileName = url.split('/')[-1]
                    download_file(urlPrincipal + urllib.quote(url.encode('utf8')), fileName)
                    libro = {
                        'titulo': titulo,
                        'extension': extension,
                        'url': urlPrincipal + url,
                        'file': fileName
                    }
                    libros.append(libro)
    return {'titulo': nombre, 'libros': libros}


def main():
    r = requests.get('http://www.dominiopublico.es/a.htm')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text)
        autores = getAutores(soup)
        print "Existen ", str(len(autores)), " autores para descargar\n"
        start = int(input("Dónde empiezo?\n"))
        end = int(input("Dónde termino?\n"))
        numActual = 1
        for autor in autores[start:end]:
            print "Descargando autor %d de %d: %s" % (numActual,end-start,autor['apellido'])
            print autor['url']
            numActual = numActual + 1
            infoAutor = getInfoAutor(autor['url'])
            autor['titulo'] = infoAutor['titulo']
            autor['libros'] = infoAutor['libros']
            if not  db.autores.find_one({'titulo': autor['titulo']}):
                db.autores.insert_one(autor)
            else:
                db.autores.update({'titulo': autor['titulo']}, autor)

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from pymongo import MongoClient
from os import path
import requests
import urllib2
import sys

import warnings
warnings.filterwarnings('ignore')

client = MongoClient('localhost', 27017)
db = client['planetalibro']

urlPrincipal = "http://planetalibro.net"


#Código para descargar archivo con barra de progreso
def downloadFile(url, nombre):
    file_name = "/media/datos/Liberascio/ServidorContenidoLibre/Libros/planetalibro/" + nombre
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
    return True

def getAutores(html):
    autores = []
    aItems = html.find_all('a', {'class': 'list-group-item'})
    for a in aItems:
        if 'http://www.planetalibro.net/autor' in a.get('href'):
            nombres = a.text.split(',')
            autor = {
                'apellido': nombres[0],
                'url': a.get('href'),
                'slug': a.get('href').split('/')[-1]
            }
            if (len(nombres) > 1):
                autor['nombre'] = nombres[1]
            autores.append(autor)
    return autores


def getLibros(url):
    libros = []
    r = requests.get(url)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text)
        aItems = soup.find_all('a', {'class': 'list-group-item'})
        for a in aItems:
            if '../libro/' in a.get('href'):
                libro = {
                    'url': a.get('href').replace('..', urlPrincipal),
                    'titulo': a.text,
                    'slug': a.get('href').split('/')[-1]
                 }
                libros.append(libro)
    return libros


def getYahooUrl(url):
    r = requests.get(url)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text)
        div = soup.find('div', {'id': 'web'})
        ol = div.find('ol', {'class': 'searchCenterMiddle'})
        if ol:
            li = ol.find('li')
            div = li.find('div', {'class': 'compTitle'})
            return div.find('h3').find('a').get('href')
        else:
            return None


def descargarLibro(libro):
    error = False
    if 'enlace-pdf' in libro:
        error = downloadFile(libro['enlace-pdf'], libro['slug']+".pdf")
    if error or not 'enlace-pdf' in libro:
        if downloadFile(libro['enlace-yahoo-result'], libro['slug']+".pdf"):
            libro['pdf'] = libro['slug'] + ".pdf"
    if 'enlace-epub' in libro:
        if downloadFile(libro['enlace-epub'], libro['slug']+".epub"):
            libro['epub'] = libro['slug'] + ".epub"


def main():
    letra = raw_input('Elija la letra de autores a descargar:\n')
    r = requests.get(urlPrincipal + "/autores/" + letra)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text)
        autores = getAutores(soup)
        start = int(input("Hay " + str(len(autores)) + " autores. Elija desde donde:\n"))
        end = int(input("Hasta dónde:\n"))
        numActual = 1
        for autor in autores[start:end]:
            print "Descargando autor %d de %d: %s" % (numActual,end-start,autor['apellido'])
            numActual = numActual + 1
            libros = getLibros(autor['url'])
            for libro in libros:
                r = requests.get(libro['url'])
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text)
                    aItems = soup.find_all('a', {'rel': 'nofollow'})
                    for a in aItems:
                        href = a.get('href')
                        if ('.pdf' in href) or ('.PDF' in href):
                            libro['enlace-pdf'] = href
                        elif ('.epub' in href) or ('.EPUB' in href):
                            libro['enlace-epub'] = href
                        elif 'ar.search.yahoo.com' in href:
                            libro['enlace-yahoo'] = href
                            libro['enlace-yahoo-result'] = getYahooUrl(href)
                    descargarLibro(libro)
            autor['libros'] = libros
            if not  db.autores.find_one({'slug': autor['slug']}):
                db.autores.insert_one(autor)
            else:
                db.autores.update({'slug': autor['slug']}, autor)

if __name__ == "__main__":
    main()

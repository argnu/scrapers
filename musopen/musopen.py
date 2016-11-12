# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from pymongo import MongoClient
from os import path,makedirs
import requests
import re
import urllib2
import sys
import shutil

import warnings
warnings.filterwarnings('ignore')

client = MongoClient('localhost', 27017)
db = client['musopen']
urlPrincipal = 'https://musopen.org/'

#Código para descargar archivo con barra de progreso
def download(url, dest):
    url = url.split('//')[1]
    url = "http://" + urllib2.quote(url.encode('utf-8'))
    if not path.isfile(dest):
        u = urllib2.urlopen(url)
        f = open(dest, 'wb')
        meta = u.info()
        file_size = int(meta.getheaders("Content-Length")[0])
        print "Descargando archivo: %s Bytes: %s" % (dest, file_size)
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


def downloadFile(url, dest):
    prevName = "/media/datos/Liberascio/ServidorContenidoLibre/Musica/musopen/files/" + url.split('/')[-1]
    if (path.isfile(prevName)):
        if not path.exists(dest): makedirs(dest)
        shutil.move(prevName, dest)
    else:
        fileName = dest + url.split('/')[-1]
        if not path.isfile(fileName):
            if not path.exists(dest): makedirs(dest)
            download(url, dest + url.split('/')[-1])



def getArtists(div):
    enlaces = div.find_all('a', {'class':'list'})
    artistas = []
    for enlace in enlaces:
        href = enlace.get('href')
        artista = {
            'url': urlPrincipal + href,
            'slug': href[16:-1]
        }
        texto = [text for text in enlace.stripped_strings][0]
        if (',' in texto):
            splits = texto.split(',')
            nombre = splits[1]
            apellido = splits[0]
            artista['nombre'] = nombre
            artista['apellido'] = apellido
        else:
            artista['apellido'] = enlace.get('title')

        artistas.append(artista)

    return artistas



def getPieces(tbody):
    pieces = []
    #cada tr(fila) es una pieza musical
    trs = tbody.find_all('tr')
    for tr in trs:
        '''
        cada td tiene información de la pieza en el siguiente orden:
        título(con enlace), forma, instrumento, rating, un botón(no se para que)
        los últimos dos los ignoro
        '''
        metadata = tr.find_all('td')
        aElem = metadata[0].find('a')
        pTitulo = [text for text in aElem.stripped_strings][0]
        pEnlace = urlPrincipal + aElem.get('href')
        pForma = metadata[1].text
        pInstrumento = metadata[2].text

        piece = {
            'titulo': pTitulo,
            'url': pEnlace,
            'forma': pForma,
            'instrumento': pInstrumento
        }
        pieces.append(piece)

    return pieces



def getSheets(url):
    sheets = []
    req = requests.get(url)

    if req.status_code == 200:
        soup = BeautifulSoup(req.text)
        tbody = soup.find('table', {'class': 'table music'}).find('tbody')

        #cada tr(fila) es una partitura de la pieza
        trs = tbody.find_all('tr')
        sheetsNum = len(trs)

        for tr in trs:
            #cada fila tiene dos td: titulo y descarga
            metadata = tr.find_all('td')
            titulo = [text for text in metadata[0].stripped_strings][0]
            if sheetsNum>1:
                urlPdf = metadata[2].find('a').get('href')
            else:
                urlPdf = metadata[1].find('a').get('href')

            sheet = {
                'titulo': titulo,
                'url': url,
                'urlFile': urlPdf,
                'file': urlPdf.split('/')[-1]
            }
            sheets.append(sheet)
    return sheets




def getSongsAndSheets(url):
    songs = []
    playerNum = 0
    req = requests.get(url)

    if req.status_code == 200:
        soup = BeautifulSoup(req.text)
        tbody = soup.find('table', {'class': 'table music'}).find('tbody')
        divDesc = soup.find('div', {'itemprop': 'about'})
        span = divDesc.find('span', {'class':'full hidden'})
        if span:
            descripcion = [text for text in span.stripped_strings][0]
        else:
            descripcion = ''

        tablePeriod = soup.find_all('div', {'class':'table-responsive'})[1]
        tdPeriod = tablePeriod.find('tbody').find('tr').find_all('td')[3]
        period = tdPeriod.find('a').text


        #cada tr(fila) es una cancion(parte) de la pieza
        trs = tbody.find_all('tr')
        songsNum = len(trs)

        scripts = soup.findAll('script')
        for script in scripts:
            if '$("#jquery_jplayer_0")' in script.text:
                scriptPlayer = script
                break

        sheets = []
        aSheets = soup.find('div', {'class': 'linked-sheet'}).find('a')
        if (aSheets):
            urlSheets = urlPrincipal + aSheets.get('href')
            sheets = getSheets(urlSheets)

        for tr in trs:
            '''
            cada td tiene información de la canción en el siguiente orden:
            - botón de play
            - titulo de canción
            - intérprete
            - licencia
            - etc.
            '''

            metadata = tr.find_all('td')
            titulo = [text for text in metadata[1].stripped_strings][0]
            interprete = [text for text in metadata[2].find('a').stripped_strings][0]
            licencia = metadata[3].find('a').get('href')

            scriptText = re.sub("\s", "", script.text.replace("\n",""))
            match = re.search('\$\("#jquery_jplayer_' + str(playerNum) + '"\)\.jPlayer\("setMedia"\,\{mp3:"https://(app|www)\.box\.com/shared/static/(\w)+\.(mp3 || wma)', scriptText)
            if (playerNum>9):
                start = match.start() + 49
            else:
                start = match.start() + 48
            end = match.end() + 3
            urlMp3 = scriptText[start:end]

            song = {
                'url': url,
                'titulo': titulo,
                'interprete': interprete,
                'licencia': licencia,
                'urlFile': urlMp3,
                'file': urlMp3.split('/')[-1]
            }
            songs.append(song)
            playerNum = playerNum + 1

        return {'songs':songs, 'sheets':sheets, 'descripcion':descripcion, 'periodo':period}




#Script principal
def main():
    url = urlPrincipal + 'music/'
    r = requests.get(url)
    start = int(sys.argv[1])
    end = int(sys.argv[2])

    if r.status_code == 200:
        soup = BeautifulSoup(r.text)
        #el primer div con clase browse-row es la lista de composers
        divMusic = soup.find('div', {'class':'browse-row'})
        artists = getArtists(divMusic)
        numActual = 1
        for artist in artists[start:end]:
            urlDownloadArtist = "/media/datos/Liberascio/ServidorContenidoLibre/Musica/" + artist['slug'] + "/"
            print "\n\nDescargando artista %d de %d: %s" % (numActual,end-start,artist['apellido'])
            numActual = numActual + 1
            reqArtist = requests.get(artist['url'])
            if reqArtist.status_code == 200:
                soupArtist = BeautifulSoup(reqArtist.text)
                table = soupArtist.find('table', {'class': 'table table-striped table-hover table-default'})
                descripcion = soupArtist.find('div', {'itemprop': 'description'})
                image = soupArtist.find('img', {'itemprop': 'thumbnailUrl'})
                if descripcion: artist['descripcion'] = descripcion.find('p').text
                if (image):
                    if not path.exists(urlDownloadArtist): makedirs(urlDownloadArtist)
                    extension = image.get('src').split('.')[-1];
                    artist['image-cropped'] = image.get('src').split('/')[-1];
                    download(image.get('src'), urlDownloadArtist + artist['image-cropped'])
                    imgCompleta = image.get('src')[0:-(15+len(extension))] + "." + extension
                    artist['image'] = image.get('src')[0:-(15+len(extension))].split('/')[-1] + "." + extension
                    download(imgCompleta, urlDownloadArtist + artist['image'])
                ulDates = soupArtist.find('ul', {'class': 'dates'})
                if ulDates.find_all('li')[2].find('span'):
                    artist['procedencia'] = ulDates.find_all('li')[2].find('span').text

                print artist['slug']
                tbody = table.find('tbody')

                pieces = getPieces(tbody)
                totalPieces = len(pieces)
                pieceNum = 1
                for piece in pieces:
                    print "     pieza %d de %d" %(pieceNum, totalPieces)
                    print "     titulo: ", piece['titulo']
                    piece['slug'] = piece['url'].split('/')[-2]
                    urlDownloadPiece = urlDownloadArtist + piece['slug'] + "/"
                    songsheets = getSongsAndSheets(piece['url'])
                    piece['songs'] = songsheets['songs']
                    for song in piece['songs']:
                        dest = urlDownloadPiece + "songs/"
                        downloadFile(song['urlFile'], dest)
                    piece['sheets'] = songsheets['sheets']
                    for sheet in piece['sheets']:
                        dest = urlDownloadPiece + "sheets/"
                        downloadFile(sheet['urlFile'], dest)
                    piece['descripcion'] = songsheets['descripcion']
                    piece['periodo'] = songsheets['periodo']
                    pieceNum = pieceNum + 1

            artist['albums'] = pieces
            if not  db.artistas.find_one({'slug': artist['slug']}):
                db.artistas.insert_one(artist)
            else:
                db.artistas.update({'slug': artist['slug']}, artist)
    print "Listo!"



if __name__ == "__main__":
    main()

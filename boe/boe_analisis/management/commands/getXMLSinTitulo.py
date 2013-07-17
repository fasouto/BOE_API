
from django.db import models
from pymongo import MongoClient
from django.core.management.base import BaseCommand, CommandError
from boe_analisis.models import Diario, Documento, Departamento, Rango, Origen_legislativo
from boe_analisis.models import Estado_consolidacion, Nota, Materia, Alerta, Palabra, Referencia
import os
import sys
from getXMLRedis import fillDocumentXMLData
from django.db.models import Q
import redis
import re
from datetime import datetime
from lxml import etree, objectify

from pattern.web import URL

class Command(BaseCommand):

    def handle(self, *args, **options):
       print 'Probando mongo'


url_s_pattern = "http://www.boe.es/diario_boe/xml.php?id=BOE-S-{0}-{1}"
url_a_pattern =  "http://www.boe.es/diario_boe/xml.php?id={0}"
url_a_html_pattern = "http://www.boe.es/diario_boe/txt.php?id={0}"

r_count = redis.StrictRedis(host='23.23.215.173', port=6379, db=0)
r = redis.StrictRedis(host='50.17.220.245', port=6379, db=0)


if (len(sys.argv) >= 3):
    rango =  sys.argv[2]

else:
    print 'manda un argumento'
    sys.exit()


max = r.llen(rango)
count = 0
test_ue = r.lrange(rango, count, count+100)

# print test_ue


while count < max:
    test_ue = r.lrange(rango, count, count+100)
    for url in test_ue:
        documento = Documento()
        fillDocumentXMLData(url, documento)
        print url
    count += 100
    print count





# print count
#
# while int(count) < max:
#     r_count.incr('count_empty', amount=10)
#     for e in test[count:count+10]:
#         url = url_a_pattern.format(e.identificador)
#         print url
#         fillDocumentXMLData(url, e)
#
#     count = int(r_count.get('count_empty'));
#



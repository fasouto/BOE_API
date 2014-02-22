__author__ = 'Carlos'
from django.db import models
from django.core.management.base import BaseCommand, CommandError
from boe_analisis.models import Diario, DocumentoAnuncio,Legislatura ,Documento, Departamento, Rango, Origen_legislativo
from boe_analisis.models import Estado_consolidacion, Nota, Materia, Alerta, Palabra, Referencia
from boe_analisis.models import Modalidad, Tipo, Tramitacion, Procedimiento,Precio
from boe_analisis.models import MateriaCPV, Materia_anuncio
import os
import sys
import locale
from django.db.models import Q
import re
from datetime import datetime
from lxml import etree, objectify

from pattern.web import URL

last_legislatura = Legislatura.objects.get_or_none(final__isnull = True)


class ProcessDocument():
    url_a_pattern =  "http://www.boe.es/diario_boe/xml.php?id={0}"
    url_a_html_pattern = "http://www.boe.es/diario_boe/txt.php?id={0}"

    xmlDoc = None
    rootXML = None
    doc = Documento()
    metadatos = None
    def __init__(self, url_xml):
        self.url = url_xml
        self.downloadXML()
        self.xmlToObject()
        self.getMetadatos()
        self.getAnalisis()
        self.createDocument()

    def saveDoc(self):
        try:
            self.doc.save()
        except:
            raise Exception

    def isDocumentoAnuncio(self):
        seccion = self.getElement(self.metadatos, 'seccion')
        subseccion = self.getElement(self.metadatos, 'subseccion')
        return seccion == '5' and subseccion == 'A'


    def processReferencias(self, doc):
        if self.existElement(self.analisis, 'referencias'):
            ref = self.analisis.referencias
            if self.existElement(ref, 'anteriores'):
                if self.existElement(ref.anteriores, 'anterior'):
                    ref_ant = []
                    for anterior in ref.anteriores.anterior:
                        doc_id = anterior.get('referencia')
                        palabra_codigo = anterior.palabra.get('codigo')
                        palabra_texto = anterior.palabra.text
                        texto = anterior.texto.text
                        palabra = self.get_or_create(Palabra, codigo=palabra_codigo, titulo=palabra_texto)
                        r = self.get_or_create(Referencia, identificador=doc_id, palabra=palabra, texto=texto)
                        ref_ant.append(r)
                    doc.referencias_anteriores = ref_ant
            if self.existElement(ref, 'posteriores'):
                if self.existElement(ref.posteriores, 'posterior'):
                    ref_post = []
                    for posterior in ref.posteriores.posterior:
                        doc_id = posterior.get('referencia')
                        palabra_codigo = posterior.palabra.get('codigo')
                        palabra_texto = posterior.palabra.text
                        texto = posterior.texto.text
                        palabra = self.get_or_create(Palabra, codigo=palabra_codigo, titulo=palabra_texto)
                        r = self.get_or_create(Referencia, identificador=doc_id, palabra=palabra, texto=texto)
                        ref_post.append(r)
                    doc.referencias_posteriores = ref_post
                    
    def createDocument(self):
        identificador = self.getElement(self.metadatos, 'identificador')
        if not identificador:
            raise Exception
        if self.isDocumentoAnuncio():
            self.doc = self.getObject(DocumentoAnuncio, identificador=identificador)
            mod_codigo, mod_titulo = self.getElementCodigoTitulo(self.analisis, 'modalidad')
            self.doc.modalidad = self.get_or_create(Modalidad, codigo=mod_codigo, titulo=mod_titulo)
            tipo_codigo, tipo_titulo = self.getElementCodigoTitulo(self.analisis, 'tipo')
            self.doc.tipo = self.get_or_create(Tipo, codigo=tipo_codigo, titulo=tipo_titulo)
            tram_codigo, tram_titulo = self.getElementCodigoTitulo(self.analisis, 'tramitacion')
            self.doc.tramitacion = self.get_or_create(Tramitacion, codigo=tram_codigo, titulo=tram_titulo)
            proc_codigo, proc_titulo = self.getElementCodigoTitulo(self.analisis, 'procedimiento')
            self.doc.procedimiento = self.get_or_create(Procedimiento, codigo=proc_codigo, titulo=proc_titulo)
            self.doc.fecha_presentacion_ofertas = self.getElement(self.analisis, 'fecha_presentacion_ofertas')
            self.doc.fecha_apertura_ofertas = self.getElement(self.analisis, 'fecha_apertura_ofertas')
            precio_codigo, precio_titulo =  self.getElementCodigoTitulo(self.analisis, 'precio')
            self.doc.precio = self.get_or_create(Precio, codigo=precio_codigo, titulo=precio_titulo)
            importe = self.getElement(self.analisis, 'importe')
            if isinstance(importe, str):
                self.doc.importe = self.stringToFloat(importe)
            self.doc.ambito_geografico = self.getElement(self.analisis, 'ambito_geografico')
            self.doc.observaciones = self.getElement(self.analisis, 'observaciones')
        else:
            self.doc = self.getObject(Documento, identificador=identificador)
        
        doc = self.doc
        doc.seccion = self.getElement(self.metadatos, 'seccion')
        doc.subseccion = self.getElement(self.metadatos, 'subseccion')
        doc.titulo = self.getElement(self.metadatos, 'titulo')
        diario_codigo, diario_titulo = self.getElementCodigoTitulo(self.metadatos, 'diario')
        doc.diario = self.get_or_create(Diario, codigo=diario_codigo, titulo=diario_titulo)
        doc.diario_numero = self.getElement(self.metadatos, 'diario_numero')
        dep_codigo, dep_titulo = self.getElementCodigoTitulo(self.metadatos, 'departamento')
        # In document BOE-B-2014-4328 there is no codigo for Departamento so make it blank for this case
        if not dep_codigo:
            dep_codigo = ""
        doc.departamento = self.get_or_create(Departamento, codigo=dep_codigo, titulo=dep_titulo)
        rango_codigo, rango_titulo = self.getElementCodigoTitulo(self.metadatos, 'rango')
        doc.rango = self.get_or_create(Rango, codigo=rango_codigo, titulo=rango_titulo)
        doc.numero_oficial = self.getElement(self.metadatos, 'numero_oficial')
        doc.fecha_disposicion = self.textToDate(self.getElement(self.metadatos, 'fecha_disposicion'))
        if doc.fecha_disposicion:
            if (doc.fecha_disposicion.date() >= last_legislatura.inicio):
                doc.legislatura =  last_legislatura
            else:
                legislatura = Legislatura.objects.get_or_none(inicio__lte = doc.fecha_disposicion, final__gte = doc.fecha_disposicion)
                if legislatura is not None:
                    doc.legislatura = legislatura


        doc.fecha_publicacion = self.textToDate(self.getElement(self.metadatos, 'fecha_publicacion'))
        doc.fecha_vigencia = self.textToDate(self.getElement(self.metadatos, 'fecha_vigencia'))
        doc.fecha_derogacion = self.textToDate(self.getElement(self.metadatos, 'fecha_derogacion'))
        doc.letra_imagen = self.getElement(self.metadatos, 'letra_imagen')
        
        doc.pagina_inicial = self.textToInt(self.getElement(self.metadatos, 'pagina_inicial'))
        doc.pagina_final = self.textToInt(self.getElement(self.metadatos, 'pagina_final'))
        doc.suplemento_pagina_inicial = self.getElement(self.metadatos, 'suplemento_pagina_inicial')
        doc.suplemento_pagina_final = self.getElement(self.metadatos, 'suplemento_pagina_final')
        doc.estatus_legislativo = self.getElement(self.metadatos, 'estatus_legislativo')
        origen_leg_cod, origen_leg_titulo = self.getElementCodigoTitulo(self.metadatos, 'origen_legislativo')
        doc.origen_legislativo = self.get_or_create(Origen_legislativo, codigo=origen_leg_cod, titulo=origen_leg_titulo)
        est_cons_cod, est_cons_titulo = self.getElementCodigoTitulo(self.metadatos, 'estado_consolidacion')
        if est_cons_cod:
            doc.estado_consolidacion = self.get_or_create(Estado_consolidacion, codigo=self.textToInt(est_cons_cod), titulo=est_cons_titulo)
        doc.judicialmente_anulada = self.SiNoToBool(self.getElement(self.metadatos, 'judicialmente_anulada'))
        doc.vigencia_agotada = self.SiNoToBool(self.getElement(self.metadatos, 'vigencia_agotada'))
        doc.estatus_derogacion = self.SiNoToBool(self.getElement(self.metadatos, 'estatus_derogacion'))
        doc.url_htm = self.url_a_html_pattern.format(doc.identificador)
        doc.url_xml = self.url_a_pattern.format(doc.identificador)
        doc.url_epub = self.getElement(self.metadatos, 'url_epub')
        doc.url_pdf = self.getElement(self.metadatos, 'url_pdf')
        doc.url_pdf_catalan = self.getElement(self.metadatos, 'url_pdf_catalan')
        doc.url_pdf_euskera = self.getElement(self.metadatos, 'url_pdf_euskera')
        doc.url_pdf_gallego = self.getElement(self.metadatos, 'url_pdf_gallego')
        doc.url_pdf_valenciano = self.getElement(self.metadatos, 'url_pdf_valenciano')
        doc.texto = etree.tostring(self.rootXML.texto, pretty_print=True)
        
        # Save doc before many_to_many relationships
        self.saveDoc()
        if self.isDocumentoAnuncio():
            doc.materias_cpv = self.getArrayOfElementsFromText(self.analisis, 'materias_cpv', MateriaCPV)
            doc.materias_anuncio = self.getArrayOfElementsFromText(self.analisis, 'materias', Materia_anuncio)
        doc.notas = self.getArrayOfElements(self.analisis, 'notas', 'nota', Nota)
        doc.materias = self.getArrayOfElements(self.analisis, 'materias', 'materia', Materia)
        doc.alertas = self.getArrayOfElements(self.analisis, 'alertas', 'alerta', Alerta)
        self.processReferencias(doc)
        

    def getArrayOfElements(self, origin, element, subelement, model):
        if self.existElement(origin, element):
            subel = getattr(origin, element)
            if self.existElement(subel, subelement):
                elements = []
                for el in getattr(subel, subelement):
                    codigo =  el.get('codigo')
                    titulo = el.text
                    if codigo:
                        ob = self.get_or_create(model, codigo=codigo, titulo=titulo)
                        elements.append(ob)
                return elements
        return []
        
    def getArrayOfElementsFromText(self, origin, element, model):
        if self.existElement(origin, element):
            parent = self.getElement(origin,element)
            if parent:
                chunks = parent.split('\n')
                cod_text_pattern = re.compile(r'(\d+)\s+(.*)')
                elements = []
                for idx,el in enumerate(chunks):
                    m = cod_text_pattern.match(el)
                    codigo = m.group(1)
                    titulo = m.group(2)
                    if codigo:
                        ob = self.get_or_create(model, codigo=codigo, titulo=titulo)
                        elements.append(ob)
                    return elements
        
        return []
        # codigo, titulo = self.getElementCodigoTitulo()
    def getElementCodigoTitulo(self, origin, element):
        codigo = None
        titulo = None
        
        cod = self.getAttribute(origin, element, 'codigo')
        tit = self.getElement(origin, element)
        
        # Assign vars if not null or empty or just spaces
        if cod:
            codigo = cod 
        if tit:
            titulo = tit.strip()
            
        return codigo, titulo

    def getAttribute(self, origin, element, attribute):
        if self.existElement(origin, element):
            return getattr(origin,element).get(attribute)
        return None
        
    def downloadXML(self):
        url_xml = URL(self.url)
        self.xmlDoc = url_xml.download()

    def xmlToObject(self):
        self.rootXML = objectify.fromstring(self.xmlDoc)

    def getMetadatos(self):
        self.metadatos = self.rootXML.metadatos

    def getAnalisis(self):
        self.analisis = self.rootXML.analisis


    def existElement(self, origin, element):
        return hasattr(origin, element)

    def getElement(self,origin, element):
        if hasattr(origin, element):
            return getattr(getattr(origin,element), 'text')


    @staticmethod
    def get_or_create(model, **kwargs):
        #print str(model)
        len_items = len(kwargs)
        count_items = 0
        for k, v in kwargs.items():
            if not v:
                count_items += 1

        if len_items == count_items:
            return None

        objeto = None
        try:
            objeto = model.objects.get(**kwargs)
        except:              
            objeto = model(**kwargs)
            try:
                objeto.save()
            except: 
                print model
        return objeto
        
    @staticmethod
    def getObject(model, **kwargs):
        objeto = None
        try:
            objeto = model.objects.get(**kwargs)
        except:    
            objeto = model(**kwargs)
        return objeto
        
    @staticmethod
    def already_processed_doc(url):
        p = re.compile(r'.*id=(.*)$')
        m = p.match(url)
        id = m.group(1)
        if id:
            try:
                objeto = Documento.objects.get(identificador=id)
                return True       
            except:
                return False
            
        return False
            
    @staticmethod
    def stringToFloat(value):

        # Remove anything not a digit, comma or period
        no_cruft = re.sub(r'[^\d,.-]', '', value)
        # Split the result into parts consisting purely of digits
        parts = re.split(r'[,.]', no_cruft)
        # ...and sew them back together
        try:
            if len(parts) == 1:
                # No delimeters found
                float_str = parts[0]
            elif len(parts[-1]) != 2:
                # >= 1 delimeters found. If the length of last part is not equal to 2, assume it is not a decimal part
                float_str = ''.join(parts)
            else:
                float_str = '%s%s%s' % (''.join(parts[0:-1]),
                                        locale.localeconv()['decimal_point'],
                                        parts[-1])

            # Convert to float
            return float(float_str)
        except:
            return None

    @staticmethod
    def textToDate(texto):
        regex = re.compile("(\d{4})(\d{2})(\d{2})")
        if texto is not None:
            match = re.match(regex, texto)
            if match != None:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                d = datetime(year,month, day)
                return d
        return None
    
    @staticmethod
    def textToInt(texto):
        regex = re.compile("(\d+)")
        if texto is not None:
            match = re.match(regex, texto)
            if match != None:
                i = int(match.group(1))
                return i
        return None

    @staticmethod
    def SiNoToBool(character):
        return character == 'S'
## -*- coding: utf-8 -*-

"""
/***************************************************************************
 Precision Agriculture
                                 A QGIS plugin
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2020-07-21
        copyright            : (C) 2020 by ASPEXIT
        email                : cleroux@aspexit.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Lisa Rollier - ASPEXIT'
__date__ = '2020-07-21'
__copyright__ = '(C) 2020 by ASPEXIT'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'


from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingUtils,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsApplication,
                       QgsVectorLayer,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterVectorDestination)



from qgis import processing 
from math import sqrt
import random

class EchantillonnagePolygone(QgsProcessingAlgorithm):
    """
    
    """ 

    OUTPUT= 'OUTPUT'
    INPUT = 'INPUT'
    INPUT_METHOD = 'INPUT_METHOD'
    INPUT_N_POINTS = 'INPUT_N_POINTS'
    INPUT_DISTANCE = 'INPUT_DISTANCE'
    INPUT_BUFFER = 'INPUT_BUFFER'
    BOOL_DISTANCE = 'BOOL_DISTANCE'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT,
                self.tr('Polygon layer'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterEnum(
                self.INPUT_METHOD,
                self.tr('Sampling method'),
                ['Random','Regular']
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_N_POINTS, 
                self.tr('Number of points (approximative value for regular sampling)'),
                QgsProcessingParameterNumber.Integer,
                10
            )
        ) 

        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_BUFFER, 
                self.tr('Minimum distance to edges (in meters)'),
                QgsProcessingParameterNumber.Double,
                5
            )
        )         
        
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.BOOL_DISTANCE,
                self.tr('Sampling with minimum distance between points (for regular sampling)')
            )
        )
       
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_DISTANCE, 
                self.tr('Minimum distance between points (for regular sampling)'),
                QgsProcessingParameterNumber.Integer,
                30
            )
        )    
        
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.OUTPUT,
                self.tr('Sampling points')
            )
        )
        
        

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        
        layer = self.parameterAsVectorLayer(parameters,self.INPUT,context)
        output_path = self.parameterAsOutputLayer(parameters,self.OUTPUT,context)
        nombre_points = self.parameterAsInt(parameters,self.INPUT_N_POINTS,context)
        method = self.parameterAsEnum(parameters,self.INPUT_METHOD,context)
        buffer_distance = self.parameterAsDouble(parameters,self.INPUT_BUFFER,context)
        
        if feedback.isCanceled():
            return {}
            
        # Tampon
        # Pour limiter l'effet de bord
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': -(buffer_distance),
            'END_CAP_STYLE': 0,
            'INPUT': parameters['INPUT'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        tampon = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']
       
        buffer_layer = QgsProcessingUtils.mapLayerFromString(tampon, context)
        
        if feedback.isCanceled():
            return {}
               
        if method == 0 :
            # Points aléatoires à l'intérieur des polygones
            alg_params = {
                'INPUT': tampon,
                'MIN_DISTANCE': None,
                'STRATEGY': 0,
                'VALUE': nombre_points,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            echantillon = processing.run('qgis:randompointsinsidepolygons', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            

        else :
            
            if parameters[self.BOOL_DISTANCE]:
                spacing = parameters[self.INPUT_DISTANCE]
            else :
                features = buffer_layer.getFeatures()
                area = 0
                for f in features:
                    geom = f.geometry()
                    area += geom.area()
                ex = buffer_layer.extent()
                xlength = ex.xMaximum() - ex.xMinimum()
                ylength = ex.yMaximum() - ex.yMinimum()
                if area != 0:
                    coef = area/(xlength*ylength)
                    D = ((xlength/ylength) +1)**2 - 4*(xlength/ylength)*(1-(nombre_points/coef))
                    a = (1-(xlength/ylength)+sqrt(D))/2
                spacing = xlength/a
            
            if feedback.isCanceled():
                return {}
            
            # Points réguliers
            rand = random.random()
            alg_params = {
                'CRS': 'ProjectCrs',
                'EXTENT': tampon,
                'INSET': spacing*rand,
                'IS_SPACING': True,
                'RANDOMIZE': False,
                'SPACING': spacing,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            point_grid = processing.run('qgis:regularpoints', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            
            if feedback.isCanceled():
                return {}
            

            # Couper
            alg_params = {
                'INPUT': point_grid['OUTPUT'],
                'OVERLAY': buffer_layer,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            pre_echantillon = processing.run('native:clip', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
                
            if feedback.isCanceled():
                return {}
            
            # De morceaux multiples à morceaux uniques
            alg_params = {
                'INPUT': pre_echantillon['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            echantillon = processing.run('native:multiparttosingleparts', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
        
        if feedback.isCanceled():
            return {}
            
        # Ajouter les coordonnees dans un vecteur
        alg_params = {
            'CRS': 'ProjectCrs',
            'INPUT': echantillon['OUTPUT'],
            'PREFIX': '',
            'OUTPUT': parameters[self.OUTPUT]
        }
        processing.run('native:addxyfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
        
        if feedback.isCanceled():
            return {}
        
        
        return{self.OUTPUT : output_path} 
   
    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "V - Sampling within polygon"

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('Sampling')
    
    def shortHelpString(self):
        short_help = self.tr(
            'Allows to carry out a sampling in a polygon. The number of '
            'points is defined by the user and several sampling schemes are available.\n\n'
            '\nprovided by ASPEXIT\n'
            'author : Lisa Rollier'
            )
        return short_help

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'sampling'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return EchantillonnagePolygone()
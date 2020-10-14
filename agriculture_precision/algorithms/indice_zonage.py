# -*- coding: utf-8 -*-

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

#import QColor

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsApplication,
                       QgsVectorLayer,
                       QgsDataProvider,
                       QgsVectorDataProvider,
                       QgsField,
                       QgsFeature,
                       QgsGeometry,
                       QgsPointXY,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterField,
                       QgsProcessingParameterBoolean,
                       
                       QgsProcessingUtils,
                       NULL,
                       QgsMessageLog)

from qgis import processing 

import numpy as np
import pandas as pd

class IndiceZonage(QgsProcessingAlgorithm):
    """
    
    """

    OUTPUT= 'OUTPUT'
    INPUT_POINTS = 'INPUT_POINTS'
    INPUT_ZONES = 'INPUT_ZONES'
    FIELD_ID = 'FIELD_ID'
    FIELD = 'FIELD'
    BOOLEAN = 'BOOLEAN'
   
  

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_POINTS,
                self.tr('Point layer'),
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_ZONES,
                self.tr('Zones layer'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        
        self.addParameter( 
            QgsProcessingParameterField( 
                self.FIELD_ID,
                self.tr( "Zones identifiant" ), 
                QVariant(),
                self.INPUT_ZONES
            ) 
        )
        
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.BOOLEAN,
                self.tr('Index calculation for all numeric fields')
            )
        )
        
        self.addParameter( 
            QgsProcessingParameterField( 
                self.FIELD, 
                self.tr( "Fields for which the zoning index is calculated" ), 
                QVariant(),
                self.INPUT_POINTS,
                type=QgsProcessingParameterField.Numeric
            ) 
        )
             
        
        
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                self.tr('File'),
                '.csv',
            )
        )
        
        

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        
        layer_points=self.parameterAsVectorLayer(parameters,self.INPUT_POINTS,context) 
        csv = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        zone_id = self.parameterAsString(parameters, self.FIELD_ID, context)
        choosed_field = self.parameterAsString(parameters, self.FIELD, context)
        
        if feedback.isCanceled():
            return {}
        

         # Joindre les attributs par localisation
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'INPUT': parameters['INPUT_POINTS'],
            'JOIN': parameters['INPUT_ZONES'],
            'JOIN_FIELDS': 'DN',
            'METHOD': 1,
            'PREDICATE': [5],
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        alg_result = processing.run('qgis:joinattributesbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        points_et_zones = QgsProcessingUtils.mapLayerFromString(alg_result['OUTPUT'],context)
       
        if feedback.isCanceled():
            return {}
        

        features = points_et_zones.getFeatures()
              
        if parameters[self.BOOLEAN] :
            #liste contenant les noms des champs (uniquement numériques)
            field_list=[field.name() for field in points_et_zones.fields() if field.type() in [2,4,6] or field.name() == zone_id] 
            # 4 integer64, 6 Real
        else :
            field_list =[choosed_field, zone_id]
      
        #on créé une matrice ou 1 ligne = 1 feature
        data = np.array([[feat[field_name] for field_name in field_list] for feat in features])
                
        #on créer le dataframe avec les données et les noms des colonnes
        df = pd.DataFrame(data, columns = field_list)
        
        #Remplacer les valeur NULL (Qvariant) en Nan de panda dataframe
        df = df.where(df!=NULL)
        
        #Mettre toutes les valeurs du dataframe en réel
        df = df.astype(float)# !!! ne va pas marcher si l'identifiant de parcelle n'est pas un chiffre 
        
       
        if feedback.isCanceled():
            return {}
        

        
        #compte du nombre de points (non NaN) dans chaque zone
        nb_points_zones = df.groupby([zone_id]).count()
        nb_points_list = nb_points_zones.values.tolist()
        #avoir la variance pour chaque zone 
        df_var_zones = df.groupby([zone_id]).var()
        df_list = df_var_zones.values.tolist()
        
        
        nb_columns=len(df_list[0])
        
        nb_points = [0 for k in range(nb_columns)]
        for i in range (len(nb_points_list)):
            for k in range(len(nb_points_list[0])):
                nb_points[k] += nb_points_list[i][k]
        #on retire les points qui ne sont pas dans les zones
        df = df.dropna(subset = ['DN'])
        
        area_weighted_variance = [0 for k in range(nb_columns)]
        #calcul de la variance pour chaque zone et pour chaque champ
        k = 0
        
        if feedback.isCanceled():
            return {}
        

        for variance in df_list :
            for i in range(nb_columns):
                prop_variance = variance[i]*(nb_points_list[k][i]/nb_points[i])
                area_weighted_variance[i] += prop_variance
            k+=1
        #calcul de la variance totale
        var_df = df.drop(columns = zone_id).var()
        var_df_list = var_df.values.tolist()
        
        if feedback.isCanceled():
            return {}
        

        #calcul de l'indice RV pour chaque champ 
        RV = []
        
        for k in range(len(var_df_list)):
            if var_df_list[k] !=0 :
                RV.append(1- (area_weighted_variance[k]/var_df_list[k]))
            else :
                RV.append(NULL)
            
        zones = df[zone_id].unique().tolist()
        nb_zones = len(zones)
        df_mean = df.drop(columns = zone_id).mean()
        mean=df_mean.tolist()
        sd = df.drop(columns = zone_id).std()
        df_CV = 100*(sd/df_mean)
        CV = df_CV.tolist()
        
        if feedback.isCanceled():
            return {}
        

        #création du fichier csv qui va contenir les données de RV
        with open(csv, 'w') as output_file:
          # write header
          line = ','.join('RV_' + name for name in field_list if name != zone_id) +','+ ','.join( 'mean_' + name for name in field_list if name != zone_id) + ',number_of_zones,' + ','.join('CV_' + name for name in field_list if name != zone_id) + '\n'
          output_file.write(line)
          line = ','.join(str(rv) for rv in RV) +',' + ','.join(str(m) for m in mean) + ',' + str(nb_zones) + ',' + ','.join(str(cv) for cv in CV) +'\n'
          output_file.write(line)
         
        
        if feedback.isCanceled():
            return {}
        

        
        return{self.OUTPUT : csv} 

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'V - Zoning index'

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
        return self.tr('Zoning')

    def shortHelpString(self):
        short_help = self.tr(
            'Allows to calculate a zoning quality indicator in relation to '
            'available auxiliary information. User should fill in the zoning '
            'vector layer, and the point vector layer to which the zoning is '
            'to be compared. \n This function calculates the variance reduction '
            '(RV) index [from Bobryk et al. (2016) Validating a Digital Soil '
            'Map with Corn Yield Data for Precision Agriculture Decision Support,'
            'Agronomy Journal, 108, 1-9]'
            '\n provided by ASPEXIT\n'
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
        return 'zoning'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return IndiceZonage()
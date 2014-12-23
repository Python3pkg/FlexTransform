'''
Created on Dec 5, 2014

@author: ahoying
'''

from lxml import etree
import SyntaxParser
import logging
import copy
import re

class CFM20Alert(object):
    '''
    Parser for CFM version 2.0 Alert XML documents
    '''

    def __init__(self):
        '''
        Constructor
        '''
        
        self.logging = logging.getLogger('FlexTransform/XMLParser/CFM20Alert')
    
    def Read(self, cfm20file, xmlparser = None):
        '''
        Parse CFM20Alert XML document. Return a dictionary object with the data from the document.
        '''
        
        root = None
        if (xmlparser is not None) :
            # Validate file against the schema when it is loaded
            tree = etree.parse(cfm20file, xmlparser)
            root = tree.getroot()
        else :
            tree = etree.parse(cfm20file)
            root = tree.getroot()
        
        ParsedData = {};
        ParsedData['DocumentHeaderData'] = {}
        ParsedData['IndicatorData'] = [];
               
        cfm20dict = SyntaxParser.XMLParser.etree_to_dict(root)
        
        # Extract CFM 2.0 version information
        if ('Version' in cfm20dict['CFMAlert']) :
            ParsedData['DocumentHeaderData']['Version'] = cfm20dict['CFMAlert']['Version']
            
        if (isinstance(cfm20dict['CFMAlert']['Alert'],list)) :
            for alert in cfm20dict['CFMAlert']['Alert'] :
                indicators = self._ProcessCFM20Alert(alert)
                if (indicators.__len__() > 0) :
                    ParsedData['IndicatorData'].extend(indicators)
        else :
            indicators = self._ProcessCFM20Alert(cfm20dict['CFMAlert']['Alert'])
            if (indicators.__len__() > 0) :
                ParsedData['IndicatorData'].extend(indicators)
                
        self._NormalizeCFM20AlertData(ParsedData)
                
        return ParsedData
               
    def Write(self, cfm20file, ParsedData):
        '''
        Take the transformed data and write it out to a new CFM version 2.0 Alert XML file
        '''
        Alerts = []
        
        self._NormalizeCFM20AlertData(ParsedData)
            
        for row in ParsedData['IndicatorData'] :
            try :
                Alert = self._BuildAlert(row)
                if (Alert) :
                    Alerts.append(Alert)
                    
            except Exception as inst :
                self.logging.exception(inst)
                
        # Name space mapping for CFM 1.3 XML documents
        CFM20_URI = "http://www.anl.gov/cfm/2.0/current/CFMAlert"
        CFM20_NS = '{%s}' % CFM20_URI
        
        XSI_URI = "http://www.w3.org/2001/XMLSchema-instance"
        XSI_NS = '{%s}' % XSI_URI
        
        NS_MAP = {None: CFM20_URI,'xsi': XSI_URI}
        
        CFM20Root = etree.Element(CFM20_NS+'CFMAlert', nsmap=NS_MAP)
        CFM20Root.set(XSI_NS+'schemaLocation', "http://www.anl.gov/cfm/2.0/current/CFMAlert/../../../resources/schemas/CFMAlert.xsd")
        CFM20Root.append(SyntaxParser.XMLParser.dict_to_etree({'Version': '2.0'}))
        
        # Parse the alert dictionaries back into XML Element trees and append to the root element
        for alert in Alerts :
            CFM20Alert = SyntaxParser.XMLParser.dict_to_etree({'Alert': alert})
            CFM20Root.append(CFM20Alert)
            
            
        # Replace entity namespaces with entity name after the XML is generated so the & doesn't get munged    
        XMLOutput = re.sub('>http://www.anl.gov/cfm/2.0/current/#', '>&cfm;', etree.tostring(CFM20Root, 
                                       pretty_print=True, 
                                       xml_declaration=True, 
                                       encoding='UTF-8', 
                                       doctype="<!DOCTYPE CFMEnvelope [\n    <!ENTITY cfm 'http://www.anl.gov/cfm/2.0/current/#'>\n    <!ENTITY tlp 'http://www.us-cert.gov/tlp/#'>\n]>"
                                       ).decode(encoding='UTF-8'))
                
        cfm20file.write(XMLOutput)
        cfm20file.close()
            
            
    def _BuildAlert(self, row):
        '''
        OrderedLists and SubLists are used to force dictionary data into the correct output order for CFM 2.0 Alert Schema validation
        '''
        
        RequiredFields = ['AlertID', 'AlertTimestamp', 'IndicatorSet', 'ReasonList', 'ActionList']
        
        # Validate required fields are present
        for field in RequiredFields :
            if (field not in row) :
                raise Exception("MissingRequiredField", "Required field %s is not present in row: %s", field, row)
            

        
        OrderedList = [];
        OrderedList.append({'AlertID': row['AlertID']})
        OrderedList.append({'AlertTimestamp': row['AlertTimestamp']})
        
        if ('RelatedList' in row and 'RelatedAlert' in row['RelatedList']) :
            if (isinstance(row['RelatedList']['RelatedAlert'], list)) :
                SubLists = []
                for relatedalert in row['RelatedList']['RelatedAlert'] :
                    SubList = [];
                    SubList.append({'RelatedID': relatedalert['RelatedID']})
                    if ('RelatedDescription' in relatedalert) :
                        SubList.append({'RelatedDescription': relatedalert['RelatedDescription']})
                    SubLists.append({'RelatedAlert': SubList})
                OrderedList.append({'RelatedList': SubLists})
            else :
                raise Exception('UnexpectedPath', 'RelatedAlert is not a list: %s', row['RelatedList']['RelatedAlert'])
           
        
        if (isinstance(row['IndicatorSet'], list)) :
            SubLists = []
            for indicator in row['IndicatorSet'] :
                SubList = [];
                SubList.append({'Type': indicator['Type']})
                SubList.append({'Constraint': indicator['Constraint']})
                SubList.append({'Value': indicator['Value']})
                SubLists.append({'Indicator': SubList})
                
            if (SubLists.__len__() == 1) :
                OrderedList.append({'IndicatorSet': SubLists[0]})
            else :
                # Create complex indicator object
                # FIXME: Current logic only permits ORs not ANDs for CFM 2.0 Alerts
                OrderedList.append({'IndicatorSet': {'CompositeIndicator': {'Or': SubLists}}})
        else :
            raise Exception('UnexpectedPath', 'IndicatorSet is not a list: %s', row['IndicatorSet'])
        
        if ('ReasonList' in row and 'Reason' in row['ReasonList']) :
            if (isinstance(row['ReasonList']['Reason'], list)) :
                SubLists = []
                for reason in row['ReasonList']['Reason'] :
                    SubList = [];
                    SubList.append({'ReasonCategory': reason['ReasonCategory']})
                    if ('ReasonDescription' in reason) :
                        SubList.append({'ReasonDescription': reason['ReasonDescription']})
                    SubLists.append({'Reason': SubList})
                OrderedList.append({'ReasonList': SubLists})
            else :
                raise Exception('UnexpectedPath', 'Reason is not a list: %s', row['ReasonList']['Reason'])

        if ('ActionList' in row and 'Action' in row['ActionList']) :
            if (isinstance(row['ActionList']['Action'], list)) :
                SubLists = []
                for action in row['ActionList']['Action'] :
                    SubList = [];
                    SubList.append({'ActionCategory': action['ActionCategory']})
                    if ('ActionDescription' in action) :
                        SubList.append({'ActionDescription': action['ActionDescription']})
                    if ('ActionTimestamp' in action) :
                        SubList.append({'ActionTimestamp': action['ActionTimestamp']})
                    SubLists.append({'Action': SubList})
                OrderedList.append({'ActionList': SubLists})
            else :
                raise Exception('UnexpectedPath', 'Action is not a list: %s', row['ActionList']['Action'])
            
        if ('Comment' in row) :
            OrderedList.append({'Comment': row['Comment']})
            
        if ('AlertExtendedAttributeType' in row) :
            if (isinstance(row['AlertExtendedAttributeType'], list)) :
                for extendedattr in row['AlertExtendedAttributeType'] :
                    SubList = [];
                    SubList.append({'Field': extendedattr['Field']})
                    SubList.append({'Value': extendedattr['Value']})
                    OrderedList.append({'AlertExtendedAttributeType': SubList})
            else :
                raise Exception('UnexpectedPath', 'AlertExtendedAttributeType is not a list: %s', row['AlertExtendedAttributeType'])
            
        return OrderedList

    def _ProcessCFM20Alert(self, alert):
        '''
        Process the alert, return one alert object for each combination of complex indicators
        '''
        
        indicators = []
        
        if ('IndicatorSet' in alert) :
            indicatorList = self._BuildIndicatorList(alert['IndicatorSet'])
            if (indicatorList.__len__() == 1) :
                alert['IndicatorSet'] = indicatorList[0]
                indicators.append(alert)
            else :
                for indicator in indicatorList :
                    newAlert = copy.deepcopy(alert);
                    newAlert['IndicatorSet'] = indicator
                    indicators.append(newAlert)
        
        return indicators
    
    def _BuildIndicatorList(self, indicatorset, operation=None):
        '''
        Process out the indicator set data, return one indicator for each combination of complex indicators
        '''
        
        indicatorList = []
        newIndicators = []
        
        for k,v in indicatorset.items() :
            if (k == 'Indicator') :
                if (isinstance(v,list)) :
                    indicatorList.extend(v)
                else :
                    indicatorList.append(v)
            elif (k == 'CompositeIndicator') :
                if ('Or' in v) :
                    newIndicators = self._BuildIndicatorList(v['Or'], operation='Or')
                    if (operation != 'And') :
                        indicatorList.extend(newIndicators)
                    
                elif ('And' in v) :
                    newIndicators = self._BuildIndicatorList(v['And'], operation='And')
                    indicatorList.append(newIndicators)
                    
                else :
                    raise Exception('InvalidOperation', 'Invalid composite indicator operation: %s' % v.items())
                
        if (operation == 'And') :
            for i in newIndicators :
                for x in indicatorList :
                    if (isinstance(x,list)) :
                        x.extend(i)
                    else :
                        x = [x,i]
                        
        return indicatorList
    
    def _NormalizeCFM20AlertData(self, ParsedData):
        '''
        Normalize the data in the indicators, convert dictionaries to arrays for elements that may have multiple values, add namespaces to values if they are missing
        '''
                
        NormalizeElementLists = {
                                'ActionList': {'Action': 'list'},
                                'ReasonList': {'Reason': 'list'},
                                'IndicatorSet': 'list',
                                'AlertExtendedAttribute': 'list'
                                }
        
        NormalizeElementValueNamespaces =   {
                                            'ActionList': {'Action': { 'ActionCategory': 'http://www.anl.gov/cfm/2.0/current/#'}},
                                            'ReasonList': {'Reason': { 'ReasonCategory': 'http://www.anl.gov/cfm/2.0/current/#'}},
                                            'IndicatorSet': {'Type': 'http://www.anl.gov/cfm/2.0/current/#', 'Constraint': 'http://www.anl.gov/cfm/2.0/current/#'},
                                            'AlertExtendedAttribute': {'Field': 'http://www.anl.gov/cfm/2.0/current/#'},
                                            }
        
        for indicator in ParsedData['IndicatorData'] :
            self._NormalizeIndicatorElements(indicator, NormalizeElementLists)
            self._NormalizeIndicatorNamespaces(indicator, NormalizeElementValueNamespaces)
            
            
    def _NormalizeIndicatorElements(self, indicator, element):
        '''
        Normalize a single indicator, use the element dictionary for processing rules on which elements should always be represented as a list
        '''
        
        if (isinstance(element,dict)) :
            for (e,v) in element.items() :
                if (e in indicator) :
                    if (isinstance(v,dict)) :
                        self._NormalizeIndicatorElements(indicator[e], element[e])
                    elif (isinstance(v,str)) :
                        if (v == 'list' and not isinstance(indicator[e], list)) :
                            newValue = indicator.pop(e)
                            indicator[e] = [newValue]

    def _NormalizeIndicatorNamespaces(self, indicator, element):
        '''
        Normalize a single indicator, use the element dictionary for processing rules on which elements should have the namespace prepended to the value
        '''
        
        if (isinstance(element,dict)) :
            for (e,v) in element.items() :
                if (isinstance(indicator,dict) and e in indicator) :
                    if (isinstance(v,dict)) :
                        self._NormalizeIndicatorNamespaces(indicator[e], element[e])
                    elif (isinstance(v,str) and v not in indicator[e]) :
                        indicator[e] = "%s%s" % (v,indicator[e])
                elif (isinstance(indicator,list)) :
                    for i in indicator :
                        self._NormalizeIndicatorNamespaces(i, element)
                        
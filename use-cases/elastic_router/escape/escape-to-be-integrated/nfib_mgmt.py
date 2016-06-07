# Copyright 2015 Sahel Sahhaf <sahel.sahhaf@intec.ugent.be>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Contains the class for managing NFIB.
"""

from collections import deque
import os
import sys


import py2neo
from py2neo import Graph, Relationship
import networkx

from py2neo.packages.httpstream.http import SocketError

from escape.orchest import log as log
try:
  from escape.nffg_lib.nffg import NFFG
except ImportError:
  import sys, os, inspect

  sys.path.insert(0, os.path.join(os.path.abspath(os.path.realpath(
    os.path.abspath(
    os.path.split(inspect.getfile(inspect.currentframe()))[0])) + "/.."),
                                  "nffg_lib/"))
  
  from nffg import NFFG
  


class NFIBManager(object):
  """
  Manage the handling of Network Function Information Base.

  Use neo4j implementation for storing and querying NFs and NF decompositions.
  """

  def __init__ (self):
    """
    Init.
    """
    super(NFIBManager, self).__init__()
    log.debug("Init %s based on neo4j" % self.__class__.__name__)
    self.__suppress_neo4j_logging()
    self.graph_db = Graph()

  @staticmethod
  def __suppress_neo4j_logging (level=None):
    """
    Suppress annoying and detailed logging of `py2neo` and `httpstream`
    packages.

    :return: None
    """
    import logging
    level = level if level is not None else logging.WARNING
    logging.getLogger("py2neo").setLevel(level)
    logging.getLogger("httpstream").setLevel(level)

  def addNode (self, node):
    """
    Add new node to the DB.

    :param node: node to be added to the DB
    :type node: dict
    :return: success of addition
    :rtype: Boolean
    """
    if node['label']=='SAP' or node['label']=='graph':

      node_db = list(
        self.graph_db.find(node['label'], 'node_id', node['node_id']))
    elif node['label']=='NF':
      node_db = list(
        self.graph_db.find(node['label'], 'functional_type', node['functional_type']))
    else:
      log.debug("node %s does not have a valid type" % node['node_id'])
      return False

    if len(node_db) > 0:
      log.debug("node %s exists in the DB" % node['node_id'])
      return False
    node_new = py2neo.Node(node['label'], node_id=node['node_id'])
    
    for key, value in node.items():
      
      node_new.properties[key] = value
    self.graph_db.create(node_new)
    return True

  def addClickNF (self, nf):
    """
    Add new click-based NF to the DB
 
    :param nf: nf to be added to the DB
    :type nf: dict
    :return: success of addition
    :rtype: Boolean
    """
    dirname = "/home/mininet/escape-shared/mininet/mininet"

    # 1. First check if the source can be compiled
    if nf.get('clickSource', ''):
      if not self.clickCompile(nf):
        return False

    # 2. Check the existence of the required VNFs/Click elements
    dependency = []
    clickTempPath = nf.get('clickTempPath',
                           dirname + '/templates/' + nf['functional_type'] + '.jinja2')
    if os.path.exists(clickTempPath):

      with open(clickTempPath) as template:
        for line in template:
          if '::' in line:
            element = line.split('::')[-1].split('(')[0].replace(' ', '')

            node = list(self.graph_db.find('NF', 'functional_type', str(element)))
            if len(node) <= 0:
              log.debug(
                "The new NF is dependent on non-existing NF %s" % element)
              return False
            else:
              dependency.append(str(element))
      template = open(clickTempPath, 'r').read()
    else:
      template = ''

    # 3. Extract the click handlers form the source files
    read_handlers = {}
    read = []
    write_handlers = {}
    write = []

    for src in nf.get('clickSource', ''):
      if '.cc' in src:
        with open(nf.get('clickPath', '') + '/' + src) as source:
          for line in source:
            if 'add_read_handler' in line:
              hdlr = line.split('"')[1]
              if hdlr not in read:
                read.append(hdlr)
            if 'add_write_handler' in line:
              hdlr = line.split('"')[1]
              if hdlr not in write:
                write.append(hdlr)
    if read:
      read_handlers[nf['functional_type']] = read
    if write:
      write_handlers[nf['functional_type']] = write

    # Add the handlers of other elements used in click scripts of the new NF
    if dependency:
      for element in dependency:
        NF_info = self.getNF(element)
        read = eval(NF_info['read_handlers']).get(element, '')
        write = eval(NF_info['write_handlers']).get(element, '')
        if read:
          read_handlers[element] = read
        if write:
          write_handlers[element] = write

    # 4. Add the NF to the DB
    nf.update(

      {'dependency': repr(dependency), 'read_handlers': repr(read_handlers),
       'write_handlers': repr(write_handlers), 'command': str(template)})

    self.addNode(nf)

  def addVMNF (self, nf):
    # To be updated
    self.addNode(nf)

  @staticmethod
  def clickCompile (nf):
    """
    Compile source of the click-based NF

    :param nf: the click-based NF
    :type nf: dict
    :return: success of compilation
    :rtype: Boolean
    """
    for src in nf.get('clickSource', ''):
      if not os.path.exists(nf.get('clickPath', '') + '/' + src):
        log.debug("source file does not exist: %s" % src)
        return False
    os.system('cd ' + nf.get('clickPath',
                             '') + '; make clean; ./configure; make elemlist; '
                                   'make')
    if not os.path.exists(nf.get('clickPath', '') + '/userlevel/click'):
      log.debug("The source code can not be compiled")
      return False
    else:
      return True

  def removeNF (self, nf_functional_type):
    """
    Remove an NF and all its decompositions from the DB.

    :param nf_functional_type: the functional_type of the NF to be removed from the DB
    :type nf_functional_type: string
    :return: success of removal
    :rtype: Boolean
    """
    node = list(self.graph_db.find('NF', 'functional_type', nf_functional_type))
    if len(node) > 0:
      rels_DECOMPOSE = list(
        self.graph_db.match(start_node=node[0], rel_type='DECOMPOSED'))
      for rel in rels_DECOMPOSE:
        self.removeDecomp(rel.end_node.properties['node_id'])
      node[0].delete_related()
      return True
    else:
      log.debug("node %s does not exist in the DB" % nf_id)
      return False

  def updateNF (self, nf):
    """
    Update the information of a NF.

    :param nf: the information for the NF to be updated
    :type nf: dict
    :return: success of the update
    :rtype: Boolean
    """
    node = list(self.graph_db.find(nf['label'], 'node_id', nf['node_id']))
    if len(node) > 0:
      node[0].set_properties(nf)
      return True
    else:
      log.debug("node %s does not exist in the DB" % nf['node_id'])
      return False

  def getNF (self, nf_functional_type):
    """
    Get the information for the NF with id equal to nf_id.
 
    :param nf_functional_type: the functional_type of the NF to get the information for
    :type nf_functional_type: string
    :return: the information of NF with id equal to nf_id
    :rtype: dict
    """
    node = list(self.graph_db.find('NF', 'functional_type', nf_functional_type))
    if len(node) > 0:
      return node[0].properties
    else:
      log.debug("node %s does not exist in the DB" % nf_id)
      return None

  def addRelationship (self, relationship):
    """
    Add relationship between two existing nodes

    :param relationship: relationship to be added between two nodes
    :type relationship: dict
    :return: success of the addition
    :rtype: Boolean
    """
    node1 = list(self.graph_db.find(relationship['src_label'], 'node_id',
                                    relationship['src_id']))
    node2 = list(self.graph_db.find(relationship['dst_label'], 'node_id',
                                    relationship['dst_id']))

    if len(node1) > 0 and len(node2) > 0:

      rel = Relationship(node1[0], relationship['rel_type'], node2[0])
      for key, value in relationship.items():
        rel.properties[key] = value
      self.graph_db.create(rel)
      return True
    else:
      log.debug("nodes do not exist in the DB")
      return False

  def removeRelationship (self, relationship):
    """
    Remove the relationship between two nodes in the DB.

    :param relationship: the relationship to be removed
    :type relationship: dict
    :return: the success of the removal
    :rtype: Boolean
    """
    node1 = list(self.graph_db.find(relationship['src_label'], 'node_id',
                                    relationship['src_id']))
    node2 = list(self.graph_db.find(relationship['dst_label'], 'node_id',
                                    relationship['dst_id']))
    if len(node1) > 0 and len(node2) > 0:
      rels = list(self.graph_db.match(start_node=node1[0], end_node=node2[0],
                                      rel_type=relationship['rel_type']))
      for r in rels:
        r.delete()
      return True
    else:
      log.debug("nodes do not exist in the DB")
      return False

  def addDecomp (self, nf_id, decomp_id, decomp):
    """
    Add new decomposition for a high-level NF.

    :param nf_functional_type: the functional_type of the NF for which a decomposition is added
    :type nf_functional_type: string
    :param decomp_id: the id of the new decomposition
    :type decomp_id: string
    :param decomp: the decomposition to be added to the DB
    :type decomp: Networkx.Digraph
    :return: success of the addition
    :rtype: Boolean
    """
    nf = list(self.graph_db.find('NF', 'node_id', nf_id))
    if len(nf) <= 0:
      log.debug("NF %s does not exist in the DB" % nf_id)
      return False

    for n in decomp.nodes():
      node = list(self.graph_db.find('SAP', 'node_id', n))
      if len(node) > 0:
        log.debug("SAPs exist in the DB")
        return False
    if not self.addNode({'label': 'graph', 'node_id': decomp_id}):
      log.debug("decomposition %s exists in the DB" % decomp_id)
      return False

    for n in decomp.nodes():

      if decomp.node[n]['properties']['label'] == 'SAP':
        self.addNode(decomp.node[n]['properties'])
        dst_label = 'SAP'

      elif decomp.node[n]['properties']['label'] == 'NF' and decomp.node[n]['properties']['deployment_type'] == 'click':

        self.addClickNF(decomp.node[n]['properties'])
        dst_label = 'NF'

      elif decomp.node[n]['properties']['label'] == 'NF' and decomp.node[n]['properties']['deployment_type'] == 'VM':

        self.addVMNF(decomp.node[n]['properties'])
        dst_label = 'NF'

      elif decomp.node[n]['properties']['label'] == 'NF' and (decomp.node[n]['properties']['deployment_type'] == 'NA' or decomp.node[n]['properties']['deployment_type'] == 'ryu' or decomp.node[n]['properties']['deployment_type'] == 'openvswitch' ):

        self.addNode(decomp.node[n]['properties'])
        dst_label = 'NF'
      

      else:
        # FIXME - czentye --> add default to dst_label variable always be
        # defined for addRelationship
        self.addNode({'label': 'NF', 'type': 'NA'})
        dst_label = 'NA'

      self.addRelationship(

        {'src_label': 'graph', 'dst_label': dst_label, 'src_id': decomp_id,
         'dst_id': n, 'rel_type': 'CONTAINS'})

    for e in decomp.edges():
      temp = {'src_label': decomp.node[e[0]]['properties']['label'],
              'src_id': e[0],
              'dst_label': decomp.node[e[1]]['properties']['label'],
              'dst_id': e[1], 'rel_type': 'CONNECTED'}

      temp.update(decomp.edge[e[0]][e[1]]['properties'])

      self.addRelationship(temp)

    self.addRelationship(

      {'src_label': 'NF', 'src_id': nf_id, 'dst_label': 'graph',
       'dst_id': decomp_id, 'rel_type': 'DECOMPOSED'})

    return True

  def removeDecomp (self, decomp_id):
    """
    Remove a decomposition from the DB.

    :param decomp_id: the id of the decomposition to be removed from the DB
    :type decomp_id: string
    :return: the success of the removal
    :rtype: Boolean
    """
    node = list(self.graph_db.find('graph', 'node_id', decomp_id))

    if len(node) > 0:
      queue = deque([node[0]])
      while len(queue) > 0:
        node = queue.popleft()

        # we search for all the nodes with relationship CONTAINS or DECOMPOSED
        rels_CONTAINS = list(
          self.graph_db.match(start_node=node, rel_type='CONTAINS'))
        rels_DECOMPOSED = list(
          self.graph_db.match(start_node=node, rel_type='DECOMPOSED'))
        if len(rels_CONTAINS) > 0:
          rels = rels_CONTAINS
        else:
          rels = rels_DECOMPOSED
        for rel in rels:
          if len(list(self.graph_db.match(end_node=rel.end_node,
                                          rel_type='CONTAINS'))) <= 1:
            queue.append(rel.end_node)
        node.isolate()
        node.delete()
      return True
    else:
      log.debug("decomposition %s does not exist in the DB" % decomp_id)
      return False

  def getSingleDecomp (self, decomp_id):
    """
    Get a decomposition with id decomp_id.
  
    : param decomp_id: the id of the decomposition to be returned
    : type decomp_id: str
    : return: decomposition with id equal to decomp_id
    : rtype: tuple of networkx.DiGraph and Relationships 
    """

    graph = networkx.DiGraph()
    node = list(self.graph_db.find('graph', 'node_id', decomp_id))

    if len(node) != 0:
      rels = list(self.graph_db.match(start_node=node[0], rel_type='CONTAINS'))
      for rel in rels:
        graph.add_node(rel.end_node.properties['node_id'])
        graph.node[rel.end_node.properties['node_id']][
          'properties'] = rel.end_node.properties
      for rel in rels:
        rel_CONNECTED = list(
          self.graph_db.match(start_node=rel.end_node, rel_type='CONNECTED'))
        for rel_c in rel_CONNECTED:
          if rel_c.end_node.properties['node_id'] in graph.nodes():
            graph.add_edge(rel_c.start_node.properties['node_id'],
                           rel_c.end_node.properties['node_id'])
            graph.edge[rel_c.start_node.properties['node_id']][
              rel_c.end_node.properties['node_id']][
              'properties'] = rel_c.properties
      return graph, rels
    else:
      log.debug("decomposition %s does not exist in the DB" % decomp_id)
      return None

  def getDecomps (self, nffg):
    """
    Get all decompositions for a given nffg.

    : param nffg: the nffg for which the decompositions should be returned
    : type nffg: nffg
    : return: all the decompositions for the given nffg
    : rtype: dict
    """
    decompositions = {}
    nodes_list = []
    index = 0
    l=list(nffg.sg_hops)
    counter = len(l)

    for n in nffg.nfs:
      
      node = list(self.graph_db.find('NF', 'functional_type', n.functional_type))
      if len(node) != 0:
        nodes_list.append((node[0],n.id))

      else:
        log.debug("NF %s does not exist in the DB" % n.id)
        return None
    

    queue = deque([nodes_list])
    queue_nffg = deque([nffg])
    while len(queue) > 0:
      nodes = queue.popleft()
      nffg_init = queue_nffg.popleft()
      indicator = 0
      for node, N_id in nodes:

        rels_DECOMPOSED = list(
          self.graph_db.match(start_node=node, rel_type='DECOMPOSED'))
        for rel in rels_DECOMPOSED:
          indicator = 1
          nffg_temp = NFFG()
          graph, rels = self.getSingleDecomp(rel.end_node.properties['node_id'])

          for n in graph.nodes():

            if graph.node[n]['properties']['label'] == 'NF':
              new_nf = nffg_temp.add_nf(id=n, 
                               name=graph.node[n]['properties']['name'],
                               func_type=graph.node[n]['properties']['functional_type'],
                               dep_type=graph.node[n]['properties']['deployment_type'],
                               cpu=graph.node[n]['properties']['cpu'],
                               mem=graph.node[n]['properties']['mem'],
                               storage=graph.node[n]['properties']['storage'])
              for m in graph.node[n]['properties'].keys():
                if 'metadata' in m:
                  new_nf.add_metadata(m.split('metadata_')[1],graph.node[n]['properties'][m])
              
                               

              #this is added for ER to support the port-sap (not connected to any NF/SAP)
              
              port_properties ={'name':graph.node[n]['properties']['port-sap-name'],'port-type':'port-sap',
                                'sap':graph.node[n]['properties']['port-sap-sap'],
                                'addresses':{'l4':graph.node[n]['properties']['port-sap-l4']}}
              if 'port-sap-control' in graph.node[n]['properties'].keys():
                port_properties['control']=graph.node[n]['properties']['port-sap-control']

              new_nf.add_port(id=0,properties=port_properties)
              

            elif graph.node[n]['properties']['label'] == 'SAP':
              nffg_temp.add_sap(id=n, name= graph.node[n]['properties']['name'] )
          
          for edge in graph.edges():
            
            for nf in list(nffg_temp.nfs):

              if nf.id == edge[0]:
                node0 = nf
              if nf.id == edge[1]:
                node1 = nf
            for sap in nffg_temp.saps:
              if sap.id == edge[0]:
                node0 = sap
              if sap.id == edge[1]:
                node1 = sap
            # FIXME - czentye --> There is a chance node0, node1 variables
            # not defined yet until here and add_port will be raise an exception
            
            flag = 0
            for port in node0.ports:
              if port.id == graph.edge[edge[0]][edge[1]]['properties']['src_port']:
                flag =1
                src = node0.ports[graph.edge[edge[0]][edge[1]]['properties']['src_port']]
                break
                
            if flag ==0:
              
              # first the port property is field based on the stored data in DB
              src_property={'name':graph.edge[edge[0]][edge[1]]['properties']['name'],'port-type':graph.edge[edge[0]][edge[1]]['properties']['port-type']}
              addresses={}
              match ={}

              for a in graph.edge[edge[0]][edge[1]]['properties'].keys():
                
                if 'address' in a:
                  if len(a.split('-'))<3:
                    addresses[a.split('-')[1]]=graph.edge[edge[0]][edge[1]]['properties'][a]
                  elif a.split('-')[1] not in addresses.keys():
                    addresses[a.split('-')[1]]={}
                    addresses[a.split('-')[1]][a.split('-')[2]]=graph.edge[edge[0]][edge[1]]['properties'][a]
                  else:
                    addresses[a.split('-')[1]][a.split('-')[2]]=graph.edge[edge[0]][edge[1]]['properties'][a]

                  src_property['addresses']=addresses
                
                if 'match' in a:
                  match[a.split('match')[1]]= graph.edge[edge[0]][edge[1]]['properties'][a]
                  src_property['match']=match

              src= node0.add_port(id=graph.edge[edge[0]][edge[1]]['properties']['src_port'],properties=src_property)

            flag = 0
            for port in node1.ports:
              if port.id == graph.edge[edge[0]][edge[1]]['properties']['dst_port']:
                flag =1
                dst= node1.ports[graph.edge[edge[0]][edge[1]]['properties']['dst_port']]
                break

            if flag ==0:
              
              # first the port property is field based on the stored data in DB
              dst_property={'name':graph.edge[edge[1]][edge[0]]['properties']['name'],'port-type':graph.edge[edge[1]][edge[0]]['properties']['port-type']}
              addresses={}
              match ={}

              for a in graph.edge[edge[1]][edge[0]]['properties'].keys():
                
                if 'address' in a:
                  if len(a.split('-'))<3:
                    addresses[a.split('-')[1]]=graph.edge[edge[1]][edge[0]]['properties'][a]
                  elif a.split('-')[1] not in addresses.keys():
                    addresses[a.split('-')[1]]={}
                    addresses[a.split('-')[1]][a.split('-')[2]]=graph.edge[edge[1]][edge[0]]['properties'][a]
                  else:
                    addresses[a.split('-')[1]][a.split('-')[2]]=graph.edge[edge[1]][edge[0]]['properties'][a]

                  dst_property['addresses']=addresses
                
                if 'match' in a:
                  match[a.split('match')[1]]= graph.edge[edge[1]][edge[0]]['properties'][a]
                  dst_property['match']=match

              dst= node1.add_port(id=graph.edge[edge[0]][edge[1]]['properties']['dst_port'],properties=dst_property)

            nffg_temp.add_sglink(src,dst, id= str(counter))

            # the requirements in terms of bandwidth and delay should be added as req_edge
            nffg_temp.add_req(src, dst, id='req'+ str(counter), delay= graph.edge[edge[0]][edge[1]]['properties']['delay'],
               bandwidth=graph.edge[edge[0]][edge[1]]['properties']['bandwidth'], sg_path=(str(counter)))
            counter+=1

          for n in nffg_init.nfs:
            nffg_temp.add_node(n)
          for n in nffg_init.saps:
            nffg_temp.add_node(n)
          for n in nffg_init.infras:
            nffg_temp.add_node(n)
          for l in nffg_init.links:
            nffg_temp.add_edge(l.src.node, l.dst.node, l)
          for l in nffg_init.sg_hops:
            nffg_temp.add_edge(l.src.node, l.dst.node, l)
          for l in nffg_init.reqs:
            nffg_temp.add_edge(l.src.node, l.dst.node, l)

          extra_nodes = []
          for l in list(nffg_temp.sg_hops): 
            
            #if node.properties['node_id'] == l.src.node.id:
            if N_id == l.src.node.id:
              
              src_port = l.src
              dst_port = l.dst 

              for edge in graph.edges():

                if graph.node[edge[1]]['properties']['label'] == 'SAP':

                  if str(src_port.id) == str(
                     graph.edge[edge[0]][edge[1]]['properties']['dst_port']):

                    for e in nffg_temp.sg_hops:
                      if e.src.node.id == edge[0] and e.dst.node.id == edge[1]:
                        nffg_temp.add_sglink(e.src, dst_port, id = str(counter))
                        nffg_temp.add_req(e.src,dst_port,id = 'req'+str(counter), delay = graph.edge[edge[0]][edge[1]]['properties']['delay'],
                          bandwidth = graph.edge[edge[0]][edge[1]]['properties']['bandwidth'],sg_path= (str(counter)))
                        counter+=1
                        extra_nodes.append(edge[1])

            #if node.properties['node_id'] == l.dst.node.id:
            if N_id == l.dst.node.id:
              dst_port = l.dst
              src_port = l.src

              for edge in graph.edges():
                if graph.node[edge[0]]['properties']['label'] == 'SAP':

                  if str(dst_port.id) == str(
                     graph.edge[edge[0]][edge[1]]['properties']['src_port']):
                    for e in nffg_temp.sg_hops:
                      if e.src.node.id == edge[0] and e.dst.node.id == edge[1]:
                        nffg_temp.add_sglink(src_port, e.dst, id = str(counter))
                        nffg_temp.add_req(src_port,e.dst, id = 'req'+str(counter), delay = graph.edge[edge[0]][edge[1]]['properties']['delay'],
                          bandwidth = graph.edge[edge[0]][edge[1]]['properties']['bandwidth'],sg_path= (str(counter)))
                        counter+=1
                        extra_nodes.append(edge[0])

          #nffg_temp.del_node(node.properties['node_id'])
          nffg_temp.del_node(N_id)
          
          for extra in extra_nodes:

            nffg_temp.del_node(extra)
          queue_nffg.append(nffg_temp)

          nodes_copy = list(nodes)
          new_nodes = map(lambda x: (x.end_node,x.end_node.properties['node_id']), rels)
          nodes_copy.remove((node,N_id))
          queue.append(nodes_copy + new_nodes)
        if indicator == 1:
          break
      if indicator == 0:
        decompositions['D' + str(index)] = nffg_init
        index += 1

    return decompositions

  def removeGraphDB (self):
    """
    Remove all nodes and relationships from the DB.
   
    :return: None
    """
    self.graph_db.delete_all()

  def __initialize (self):
    """
    Initialize NFIB with test data.
    """
    log.info("Initializing NF database with NFs and decompositions...")
    # start clean - all the existing info is removed from the DB
    self.removeGraphDB()

    # add new high-level NF to the DB, all the information related to the NF
    # should be given as a dict
    self.addNode({'label': 'NF', 'node_id': 'fwd-abstract','name':'FWD-ABSTRACT','functional_type': 'forwarder', 'deployment_type': 'NA'})
    self.addNode({'label': 'NF', 'node_id': 'comp-abstract','name':'COMP-ABSTRACT','functional_type': 'compressor', 'deployment_type': 'NA'})
    self.addNode({'label': 'NF', 'node_id': 'decomp-abstract','name':'DECOMP-ABSTRACT','functional_type': 'decompressor', 'deployment_type': 'NA'})

    #add new high-level NF to the DB for ER
    self.addNode({'label':'NF','node_id': 'er','name':'ER','functional_type':'router','deployment_type': 'NA' })

    log.debug(
      "%s: high-level NFs were added to the DB" % self.__class__.__name__)

    # generate a  decomposition for a high-level forwarder NF (in form of
    # networkx)
    G1 = networkx.DiGraph()
    G1.add_path(['SAP1', 'fwd-additional', 'SAP2'])

    # create node properties
    for n in G1.nodes():
      properties = {'node_id':n}

      if 'SAP' in n:
        properties['label'] = 'SAP'
        properties['name'] = n

      else:
        properties['name'] = 'FORWARDER'
        properties['functional_type'] = 'simpleForwarder'
        properties['label'] = 'NF'
        properties['deployment_type'] = 'click'
        properties['cpu'] = 1
        properties['mem'] = 1
        properties['storage'] = 0
      G1.node[n]['properties'] = properties

    # create edge properties
    properties = {'bandwidth': 1, 'src_port': 1, 'dst_port': 1}
    G1.edge['SAP1']['fwd-additional']['properties'] = properties

    properties1 = {'bandwidth': 1, 'src_port': 1, 'dst_port': 1}
    G1.edge['fwd-additional']['SAP2']['properties'] = properties1

    # generate a decomposition for a high-level compressor NF (in form of
    # networkx)
    G2 = networkx.DiGraph()
    G2.add_path(['SAP3', 'comp-additional', 'SAP4'])

    # create node properties
    for n in G2.nodes():
      properties = {'node_id': n}
      if 'SAP' in n:
        properties['label'] = 'SAP'
        properties['name'] = n
      else:
        properties['name'] = 'COMPRESSOR'
        properties['functional_type'] = 'headerCompressor'
        properties['label'] = 'NF'
        properties['deployment_type'] = 'click'
        properties['cpu'] = 2
        properties['mem'] = 2
        properties['storage'] = 0
      G2.node[n]['properties'] = properties

    # create edge properties 
    properties3 = {'bandwidth': 2, 'src_port': 1, 'dst_port': 1}
    G2.edge['SAP3']['comp-additional']['properties'] = properties3

    properties4 = {'bandwidth': 2, 'src_port': 1, 'dst_port': 1}
    G2.edge['comp-additional']['SAP4']['properties'] = properties4

    # generate a decomposition for a high-level decompressor NF (in form of
    # networkx)
    G3 = networkx.DiGraph()
    G3.add_path(['SAP5', 'decomp-additional', 'SAP6'])

    # create node properties
    for n in G3.nodes():
      properties = {'node_id': n}
      if 'SAP' in n:
        properties['label'] = 'SAP'
        properties['name'] = n
      else:
        properties['name'] = 'DECOMPRESSOR'
        properties['functional_type'] = 'headerDecompressor'
        properties['label'] = 'NF'
        properties['deployment_type'] = 'click'
        properties['cpu'] = 3
        properties['mem'] = 3
        properties['storage'] = 3
      G3.node[n]['properties'] = properties

    # create edge properties
    properties5 = {'bandwidth': 3, 'src_port': 1, 'dst_port': 1}
    G3.edge['SAP5']['decomp-additional']['properties'] = properties5

    properties6 = {'bandwidth': 3, 'src_port': 1, 'dst_port': 1}
    G3.edge['decomp-additional']['SAP6']['properties'] = properties6

    G4 = self.createER()
    

    # required elementary NFs should be added first to the DB
    #self.addClickNF({'label': 'NF', 'node_id': 'Queue', 'type:': 'click'})
    #self.addClickNF({'label': 'NF', 'node_id': 'Classifier', 'type': 'click'})
    #self.addClickNF({'label': 'NF', 'node_id': 'Counter', 'type': 'click'})
    #self.addClickNF({'label': 'NF', 'node_id': 'RFC2507Comp', 'type': 'click'})
    #self.addClickNF(
     # {'label': 'NF', 'node_id': 'RFC2507Decomp', 'type': 'click'})

    # the NF decompositions are added to the DB
    self.addDecomp('fwd-abstract', 'G1', G1)
    self.addDecomp('comp-abstract', 'G2', G2)
    self.addDecomp('decomp-abstract', 'G3', G3)
    self.addDecomp('er', 'G4', G4)

    log.debug(
      "%s: NF decompositions were added to the DB" % self.__class__.__name__)

  def createER(self):

    # Generate decomposition rules for the high-level ER
    G = networkx.DiGraph()
    G.add_nodes_from(['SAP7','SAP8','SAP9','SAP10','ovs','ctrl'])

    # create node properties
    for n in G.nodes():
      properties = {'node_id': n}

      if 'SAP' in n:
        properties['label'] = 'SAP'
        properties['name'] = n

      elif n=='ctrl':
        properties['name'] = 'CONTROLLER'
        properties['functional_type'] = 'ctrl'
        properties['label'] = 'NF'
        properties['deployment_type'] = 'ryu'

        # TODO: should find a solution/ nested dict does not work in Neo4j
        properties['port-sap-name'] = "public-cfor-port"
        properties['port-sap-sap']= "INTERNET"
        properties['port-sap-control']="http://<escape ip>:8889"
        properties['port-sap-l4']="tcp/22"
        properties['cpu'] = 0
        properties['mem'] = 0
        properties['storage'] = 0

      elif n=='ovs':
        properties['name'] = 'OVS'
        properties['functional_type'] = 'ovs1'
        properties['label'] = 'NF'
        properties['deployment_type'] = 'openvswitch'
        properties['port-sap-name'] = "public-port"
        properties['port-sap-sap']="INTERNET"
        properties['port-sap-l4']="tcp/22"
        properties['metadata_VNF_NAME']="ovs1"
        properties['metadata_OVS_DPID']="9900000000000001"
        properties['metadata_CONTROLLER']="tcp:10.0.10.100:6633"
        properties['cpu'] = 0
        properties['mem'] = 0
        properties['storage'] = 0
      G.node[n]['properties'] = properties
    # create edges
    G.add_edges_from([('SAP7','ovs'),('ovs','SAP7'),('SAP8','ovs'),('ovs','SAP8'),('SAP9','ovs'),('ovs','SAP9'),('SAP10','ovs'),('ovs','SAP10'),('ctrl','ovs'),('ovs','ctrl')])
    G.edge['ovs']['ctrl']['properties'] = {'bandwidth': 10, 'src_port': 1, 'dst_port': 1, 'name':'control-port',"port-type":"port-abstract","address-l2":"00:00:00:00:00:01","address-l3-id":"addr-ctrl","address-l3-configure":"False","address-l3-requested":"10.0.10.1/24","address-l3-provided":""}
    G.edge['ctrl']['ovs']['properties'] = {'bandwidth': 10, 'src_port': 1, 'dst_port': 1,'name':"control-port","port-type":"port-abstract",'match1':"ether_type=0x800,dest_ip=10.0.10.1","match2":"ether_type=0x806,dest_mac=00:00:00:00:00:01","address-l3-id":"addr-ctrl","address-l3-configure":"False","address-l3-requested":"10.0.10.100/24"}
    G.edge['SAP7']['ovs']['properties'] = {'bandwidth': 10, 'src_port': 1, 'dst_port': 2}
    G.edge['ovs']['SAP7']['properties'] = {'bandwidth': 10, 'src_port': 2, 'dst_port': 1,"name":"ovs1_eth0","port-type":"port-abstract"}
    G.edge['SAP8']['ovs']['properties'] = {'bandwidth': 10, 'src_port': 2, 'dst_port': 3}
    G.edge['ovs']['SAP8']['properties'] = {'bandwidth': 10, 'src_port': 3, 'dst_port': 2,"name":"ovs1_eth1","port-type":"port-abstract"}
    G.edge['SAP9']['ovs']['properties'] = {'bandwidth': 10, 'src_port': 3, 'dst_port': 4}
    G.edge['ovs']['SAP9']['properties'] = {'bandwidth': 10, 'src_port': 4, 'dst_port': 3,"name":"ovs1_eth2","port-type":"port-abstract"}
    G.edge['SAP10']['ovs']['properties'] = {'bandwidth': 10, 'src_port': 4, 'dst_port': 5}
    G.edge['ovs']['SAP10']['properties'] = {'bandwidth': 10, 'src_port': 5, 'dst_port': 4,"name":"ovs1_eth3","port-type":"port-abstract"}

    return G


  def initialize (self):
    """
    Initialize NFIB with test data.
    """
    try:
      self.__initialize()

    except SocketError as e:
      
      log.error(
        "NFIB is not reachable due to failed neo4j service! Cause: " + str(e))
    except KeyboardInterrupt:
      log.warning("NFIB was interrupted by user!")
    except:


      log.error("Got unexpected error during NFIB initialization! Cause:")
      #log.error(reduce(lambda x, y: str(x) + " " + str(y), sys.exc_info()))
      raise


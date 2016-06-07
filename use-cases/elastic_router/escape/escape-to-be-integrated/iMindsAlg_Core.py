"""
Core functions and classes of iMinds Algorithm.
"""
import sys
import copy
import numpy
from collections import deque

import networkx as nx
import Alg1_Helper as helper
try:
	from escape.orchest.nfib_mgmt import NFIBManager
except ImportError:
	import sys, os, inspect

	sys.path.insert(0, os.path.join(os.path.abspath(os.path.realpath(
		os.path.abspath(
		os.path.split(inspect.getfile(inspect.currentframe()))[0])) + "/.."),
                                  "escape/escape/orchest/"))
	
	from nfib_mgmt import NFIBManager

try:
	from escape.util.nffg import NFFG
	from escape.util.nffg_elements import *
except ImportError:
	import sys, os, inspect

	sys.path.insert(0, os.path.join(os.path.abspath(os.path.realpath(
		os.path.abspath(
		os.path.split(inspect.getfile(inspect.currentframe()))[0])) + "/.."),
                                  "pox/ext/escape/util/"))
	from nffg import NFFG
	from nffg_elements import *

class iMindsAlgorithm(object):
	def __init__ (self, net0, req0, requirements0, btNr=10):

		
		self.log = helper.log.getChild(self.__class__.__name__)
		self.log.info("Initializing algorithm variables")
		
		self.req0 = copy.deepcopy(req0)
		self.net0 = copy.deepcopy(net0)
		self.requirements0 = requirements0

		# if there is no requirement in terms of bandwidth and delay set bandwidth to 0 and delay to inf
		for l in req0.sg_hops:
			if (l.src.node.id,l.dst.node.id) not in self.requirements0.keys():
				self.requirements0[(l.src.node.id,l.dst.node.id)] ={'bandwidth': 0 , 'delay':numpy.Inf}

		self.backtrackNumber = btNr
    	
		# The networkx graphs from the NFFG should be enough for the algorithm
		self.net = self.net0.network
		self.req = self.req0.network


	def start (self):

		NFIB = NFIBManager()

		# 1- retrieve all possible decompositions for the request
		
		decomps = NFIB.getDecomps(self.req0)
		if decomps==None:
			self.log.info("Could not retrieve decompositions for the requested NFs")

		# 2- calculate clusters and cluster factor
		decompCF, decompCluster = self.clusterFactor(decomps)

		# 3- select minimum cost decomp
		self.decompSelection(decomps, decompCF)
		#print self.selectedDecomp.dump()
		#self.requirements0 should be updated according to the requirements of the selected decomposed NFFG (self.selectedDecomp)
		edgereqdict = {}
		edgereqlist = []
		for req in self.selectedDecomp.reqs:
			edgereqlist.append(req)
			self.selectedDecomp.del_edge(req.src, req.dst, req.id)
    
  		# construct dict of requirements from EdgeReqs (only linklocal req are considered)
		for req in edgereqlist:

			if len(req.sg_path) == 1:
      
				reqlink = None
				for sg_link in self.selectedDecomp.sg_hops:
					if sg_link.id == req.sg_path[0]:
						reqlink = sg_link
						break
				requirement={}
				if req.delay is not  None:
					requirement['delay'] = req.delay
				else:
					requirement['delay'] = numpy.Inf

				if req.bandwidth is not  None:
					requirement['bandwidth'] = req.bandwidth
				else:
					requiremnet['bandwidth'] = 0

				edgereqdict[(sg_link.src.node.id,sg_link.dst.node.id)] = requirement
		self.requirements0.update(edgereqdict)

  		
		cluster = decompCluster[self.selectedDecompName]



		# 4- sort the NFs of each cluster based on their resource demands
		for i in range(len(cluster)):
			cluster[i] = sorted(cluster[i], key= lambda node: node.resources['cpu']+node.resources['mem']+node.resources['storage'], reverse = True)
		# 5- sort the clusters based on the demands of the NFs within each cluster
		sortedCluster = sorted(cluster, key = lambda node:node[0].resources['cpu']+ node[0].resources['mem']+node[0].resources['storage'], reverse = True)

		# 6- create a list of the sorted NFs
		sortedNFs = []
		for i in range(len(sortedCluster)):
			for j in range(len(sortedCluster[i])):
				if sortedCluster[i][j].type!='SAP':
					sortedNFs.append(sortedCluster[i][j])


		
		mappedNFs = {}
		mappedLinks = {}
		i = 0
		counter = 0

		# TODO: should check for the already mapped NFs

		# SAP mapping can be done here based on their names
		try:

			for nf, dv in self.selectedDecomp.network.nodes_iter(data=True):

				if dv.type == 'SAP':

					sapname = dv.name
					sapfound = False
					for n, dn in self.net0.network.nodes_iter(data=True):

						if dn.type == 'SAP' and dn.name == sapname:
							mappedNFs[nf]=n
							sapfound = True
							break
			if not sapfound:

				self.log.error("No SAP found in network with name: %s" % sapname)
            	
				raise uet.MappingException(
              		"No SAP found in network with name: %s. SAPs are mapped "
              		"exclusively by their names." % sapname,
              		backtrack_possible = False)
		except AttributeError as e:
			raise uet.BadInputException("Node data with name %s" % str(e),
                                "Node data not found")

		# 7- start mapping of NFs in the sortedNFs list:

		while i<len(sortedNFs):


			if counter > self.backtrackNumber:	
				# it means that after backtracking for 'backtrackNumber' times, no mapping is found
				self.log.info("No mapping found after %d time backtracking" % backtrackNumber)
				return None

			nf = sortedNFs[i]
			index = 0
			uncheckedCandidates = []
			tempLength = {}
			
			# The mapping is only for NFs, the SAP mapping is already done

			if len(self.selectedDecomp.network.node[nf.id]['candidate']) == 0:

				# If there is no candidate found for the NFs of the selected decomposition, there is no possibility for the mapping of this nf and this request
				self.log.info("No physical node can host the NF: %s" % nf.id)
				return None

			if 'unsuccess' not in self.selectedDecomp.network.node[nf.id]:
				setattr(self.selectedDecomp.network.node[nf.id],'unsuccess',[])
				
			# create a list of unchecked candidates
			for c in self.selectedDecomp.network.node[nf.id]['candidate']:
				if c.id not in self.selectedDecomp.network.node[nf.id]['unsuccess']:
					uncheckedCandidates.append(c)

			# sort the candidates based on their distance to the nodes already used in the mapping
			if len(mappedNFs) >0:
				for c in uncheckedCandidates:
					length = nx.single_source_shortest_path_length(self.net,c.id)
					selectedMinLength = numpy.Inf
					for l in length.keys():
						if l in mappedNFs.values() and length[l]<selectedMinLength:
							selectedMinLength = length[l]

					tempLength[c.id] =  selectedMinLength
				sortedCandidates = sorted (uncheckedCandidates, key = lambda node:tempLength[node.id])
			else:
				sortedCandidates = sorted (uncheckedCandidates, key = lambda node: node.resources['cpu']+ node.resource['mem']+node.resources['storage'],reverse =True)

			while True:

				if index >= len(sortedCandidates): # this indicates that this NF cannot be mapped so we should backtrack
					counter +=1
					i-=1
					if i==-1:
						self.log.info("all the previously mapped NFs and all their candidates were checked. No mapping was found")
						return None

					del self.selectedDecomp.network.node[nf.id]['unsuccess'][:]
					self.selectedDecomp.network.node[sortedNFs[i].id]['unsuccess'] = self.selectedDecomp.network.node[sortedNFs[i].id]['unsuccess']+ [mappedNFs[sortedNFs[i].id]]

					# The reserved resources for the previous mapping should be released
					self.updateResources(sortedNFs[i],mappedNFs[sortedNFs[i].id],mappedLinks)
					del mappedNFs[sortedNFs[i].id]
					for neigh in self.nfNeighbors(sortedNFs[i].id,self.selectedDecomp):
						if (neigh.id,sortedNFs[i].id) in mappedLinks.keys():
							del mappedLinks[(neigh.id,sortedNFs[i])]
						else:
							if (sortedNFs[i].id,neigh.id) in mappedLinks.keys():
								del mappedLinks[(sortedNFs[i].id,neigh.id)]

					i-=1
					break
				
				success,links = self.mapping(nf,sortedCandidates[index],mappedNFs)
				if success:
					mappedNFs[nf.id] =  sortedCandidates[index].id
					mappedLinks.update(links)
					break
				self.selectedDecomp.network.node[nf.id]['unsuccess'] = self.selectedDecomp.network.node[nf.id]['unsuccess'] + [sortedCandidates[index].id]
				index+=1

			i+=1
		#print "test",mappedNFs, mappedLinks
		return self.constructOutputNFFG(mappedNFs,mappedLinks),mappedNFs
		
	def clusterFactor(self, decomp):
		'''
		Claculate the clusters of the decompositions
		:param decomp: decompositions of a request
		:type decomp: dictionary of NFFG
		:return: The clusters and cluster factor of decompsoitions
		:rtype:dictionary, dictionary

		'''

		decompCF={}
		decompCluster ={}
		for d in decomp.keys():

			visited = {}
			cluster = 0
			clusters = []
			for node in decomp[d].nfs:
				
				if node.id not in visited.keys():
					queue = deque([node])
					visited[node.id] = 1
					cluster += 1
					temp_cluster = []
					while len(queue) != 0 :
						n = queue.popleft()

						# get all the NF neighbors of n
						neighbors = self.nfNeighbors(n.id, decomp[d])

						temp_cluster.append(n)
						for neigh in neighbors:

							if neigh.id not in visited.keys() and neigh.type!= 'SAP' and n.deployment_type == neigh.deployment_type:
								
								queue.extend([neigh])
								visited[neigh.id] = 1

					clusters.append(temp_cluster)
			decompCF[d] = cluster
			decompCluster[d] = clusters

		return decompCF, decompCluster
		
	def nfNeighbors(self, nf_id , nffg):
		'''
		find all the neighbors with type SAP and NF for a given NF
		:param nf_id: id of the nf to find the neighbors for
		:type nf_id: string
		:param nffg: the nffg in which the neighbors should be found
		:type nffg: nffg
		:return: neighbors
		:rtype: list of Node
		'''

		neighbors = list(nffg.network.node[id] for id in 
    			nffg.network.successors(nf_id) if 
    			nffg.network.node[id].type == Node.NF)+ list(nffg.network.node[id] for id in 
    			nffg.network.predecessors(nf_id) if 
    			nffg.network.node[id].type == Node.NF)+ list(nffg.network.node[id] for id in 
    			nffg.network.predecessors(nf_id) if 
    			nffg.network.node[id].type == Node.SAP) + list(nffg.network.node[id] for id in 
    			nffg.network.successors(nf_id) if 
    			nffg.network.node[id].type == Node.SAP)
		return neighbors

	def decompSelection(self, decomp, decompCF, a = 0.25, b = 0.25, g = 0.5):
		"""
		Calculate cost for each decompsoition and select minimum cost decomposition to be mapped 
		:param decomp: all possible decompositions for a request
		:type decomp: dictionary of NFFG
		:param decompCF: the cluster factor of decompositions
		:type decompCF: dictionary of int
		"""
		# calculate the candidate physical nodes
		p = {}
		for d in decomp.keys():
			nr_candidates = []
			for nf in decomp[d].nfs:

				candidate = []
				
				for infra in self.net0.infras:

					#if infra.infra_type == nf.deployment_type  and infra.resources['cpu'] >= nf.resources['cpu'] and infra.resources['mem'] >=nf.resources['mem'] and infra.resources['storage'] >= nf.resources['storage']:
					if nf.functional_type in infra.supported  and infra.resources['cpu'] >= nf.resources['cpu'] and infra.resources['mem'] >=nf.resources['mem'] and infra.resources['storage'] >= nf.resources['storage']:
						candidate.append(infra)

				setattr(decomp[d].network.node[nf.id], 'candidate', candidate)
				nr_candidates.append(len(candidate))

			p[d] = min(nr_candidates)

		minimum_cost = numpy.Inf
		selectedDecomp = None
		selectedDecompName = None

		for d in decomp.keys():
			cost = a * 1/(float(p[d]) + 0.00001) + b * decompCF[d] + g * len(list(decomp[d].nfs))
			if cost < minimum_cost:
				minimum_cost = cost
				selectedDecomp = decomp[d]
				selectedDecompName = d

		self.selectedDecomp = selectedDecomp
		self.selectedDecompName = selectedDecompName

	def _retrieveOrAddVNF (self, nffg, vnfid):

		if vnfid not in nffg.network:

			nodenf = copy.deepcopy(self.selectedDecomp.network.node[vnfid])
			nffg.add_node(nodenf)

		else:
			nodenf = nffg.network.node[vnfid]
		return nodenf

	def constructOutputNFFG (self, mappedNFs, mappedLinks):

		'''
		Construct the output NFFG with the mapping information 
		:param mappedNFs: the mapping between NFs and the physical nodes
		:type mappedNFs: dictionary 
		:param mappedLinks: the mappings between links and paths in the physical network
		:type mappedLinks: dictionary
		:return: the mapped NFFG
		:rtype: NFFG
		'''
		# start with the initial nffg received from lower layer
		# and add the mapping of the NFs and links to it
		nffg = self.net0

		for nf in mappedNFs.keys():
			if self.selectedDecomp.network.node[nf].type == 'NF':
				mappednodenf = self._retrieveOrAddVNF(nffg, nf)

				for i, j, k, d in self.selectedDecomp.network.out_edges_iter([nf], data = True, keys = True):
    				# i is always nf 
    				# Generate only ONE InfraPort for every Port of the NF-s with
    				# predictable port ID. Format: <<InfraID|NFID|NFPortID>>
					infra_port_id = "|".join((str(mappedNFs[nf]), str(nf),str(d.src.id)))
    				# WARNING: PortContainer's "in" operator needs a Port object!!
          			# We need to use try catch to test inclusion for port ID
					try:
						out_infra_port = nffg.network.node[mappedNFs[nf]].ports[infra_port_id]
						self.log.debug("Port %s found in Infra %s leading to port %s of NF"
                           " %s."%(infra_port_id, mappedNFs[nf], d.dst.id, nf))
					except KeyError:
						out_infra_port = nffg.network.node[mappedNFs[nf]].add_port(id=infra_port_id)
						self.log.debug("Port %s added to Infra %s to NF %s." 
                           % (out_infra_port.id, mappedNFs[nf], nf))

            			# this is needed when an already mapped VNF is being reused from an 
            			# earlier mapping, and the new SGHop's port only exists in the 
            			# current request. WARNING: no function for Port object addition!
            			# TODO: this is not supported yet!
						try:
							mappednodenf.ports[d.src.id]
						except KeyError:
							mappednodenf.add_port(id = d.src.id, properties = d.src.properties)
              			# use the (copies of the) ports between the SGLinks to
            			# connect the VNF to the Infra node.
            			# Add the mapping indicator DYNAMIC link only if the port was just
            			# added. NOTE: In case of NOT FULL_REMAP, the VNF-s left in place 
            			# still have these links. In case of (future) VNF replacement, 
            			# change is required here!
						nffg.add_undirected_link(out_infra_port, mappednodenf.ports[d.src.id],
                                     dynamic=True)
					helperlink = mappedLinks[(i,j)]
					if 'infra_ports' in helperlink: 
						mappedLinks[(i,j)]['infra_ports'][0] = out_infra_port
					else:
						mappedLinks[(i,j)]['infra_ports'] = [out_infra_port, None]
				for i,j,k,d in self.selectedDecomp.network.in_edges_iter([nf], data=True, keys= True):
            		# j is always vnf
					infra_port_id = "|".join((str(mappedNFs[nf]),str(nf),str(d.dst.id)))
					try:
						in_infra_port = nffg.network.node[mappedNFs[nf]].ports[infra_port_id]
						self.log.debug("Port %s found in Infra %s leading to port %s of NF"
                           " %s."%(infra_port_id, mappedNFs[nf], d.dst.id, nf))
					except KeyError:
						in_infra_port = nffg.network.node[mappedNFs[nf]].add_port(id=infra_port_id)
						self.log.debug("Port %s added to Infra %s to NF %s." 
                           % (in_infra_port.id, mappedNFs[nf], nf))
						try:
							mappednodenf.ports[d.dst.id]
						except KeyError:
							mappednodenf.add_port(id = d.dst.id, properties = d.dst.properties)
						nffg.add_undirected_link(in_infra_port, mappednodenf.ports[d.dst.id],
                                     dynamic=True)
					helperlink = mappedLinks[(i,nf)]
					if 'infra_ports' in helperlink:         			
                    
						mappedLinks[(i,nf)]['infra_ports'][1] = in_infra_port
					else:
						mappedLinks[(i,nf)]['infra_ports'] = [None, in_infra_port]
            			# Here a None instead of a port object means that the
            			# SGLink`s beginning or ending is a SAP.
		for nf in self.selectedDecomp.network.nodes_iter():
			for i, j, k, d in self.selectedDecomp.network.out_edges_iter([nf], data=True, keys=True):
        		# i is always vnf

				self._addFlowrulesToNFFGDerivatedFromReqLinks(nf, j, k, nffg, mappedNFs, mappedLinks)
        # all VNFs are added to the NFFG, so now, req ids are valid in this
    	# NFFG instance. Ports for the SG link ends are reused from the mapped NFFG.
    	# Add all the SGHops to the NFFG keeping the SGHops` identifiers, so the
    	# installed flowrules and TAG-s will be still valid
		try:
			for i, j, d in self.selectedDecomp.network.edges_iter(data=True):
				if self.selectedDecomp.network.node[i].type == 'SAP':
          			# if i is a SAP we have to find what is its ID in the network
          			# d.id is the link`s key
					sapstartid = self.getIdOfChainEnd_fromNetwork(i,mappedNFs)
					if self.selectedDecomp.network.node[j].type == 'SAP':

						sapendid = self.getIdOfChainEnd_fromNetwork(j,mappedNFs)
						nffg.add_sglink(nffg.network.node[sapstartid].ports[
                 			self._addSAPportIfNeeded(nffg, sapstartid, d.src.id)],
                            nffg.network.node[sapendid].ports[
                 			self._addSAPportIfNeeded(nffg, sapendid, d.dst.id)], 
                            id=d.id, flowclass=d.flowclass)
					else:
						nffg.add_sglink(nffg.network.node[sapstartid].ports[
						self._addSAPportIfNeeded(nffg, sapstartid, d.src.id)],
                            nffg.network.node[j].ports[d.dst.id], id=d.id,
                            flowclass=d.flowclass)
				elif self.selectedDecomp.network.node[j].type =='SAP':
					sapendid = self.getIdOfChainEnd_fromNetwork(j,mappedNFs)
					nffg.add_sglink(nffg.network.node[i].ports[d.src.id],
                          nffg.network.node[sapendid].ports[
                            self._addSAPportIfNeeded(nffg, sapendid, d.dst.id)],
                          id=d.id, flowclass=d.flowclass)
				else:
					nffg.add_sglink(nffg.network.node[i].ports[d.src.id],
                          nffg.network.node[j].ports[d.dst.id], id=d.id,
                          flowclass=d.flowclass)
		except RuntimeError as re:
			raise uet.InternalAlgorithmException("RuntimeError catched during SGLink"
          		" addition to the output NFFG. Not Yet Implemented feature: keeping "
          		"already mapped SGLinks in place if not full_remap. Maybe same SGLink "
          		"ID in current request and a previous request?")
		return nffg

	def _addSAPportIfNeeded(self, nffg, sapid, portid):
		"""
    	The request and substrate SAPs are different objects, the substrate does not
    	neccessarily have the same ports which were used by the service graph.
    	"""
    
		if portid in [p.id for p in nffg.network.node[sapid].ports]:
			return portid
		else:
			return nffg.network.node[sapid].add_port(portid).id

	def getIdOfChainEnd_fromNetwork (self, id, mappedNFs):
		"""
    	SAPs are mapped by their name, NOT by their ID in the network/request
    	graphs. If the chain is between VNFs, those must be already mapped.
    	Input is an ID from the request graph. Return -1 if the node is not
    	mapped.
		"""
		ret = -1
		for v in mappedNFs.keys():
			if v == id:
				ret = mappedNFs[v]
				break
		return ret

	def mapping(self,nf,infra,mappedNFs):
		"""
		Check if the mapping of a NF to a given infrastructure node is feasible
		:param nf: the new nf to be mapped 
		:type nf: Node
		:param infra: the infrastructure node to be checked for the mapping 
		:type infra: Node
		:param mappedNFs: the mapping between NFs and the infrastructure nodes
		:type mappedNFs: dictionary
		:return: success of the mapping and the node mappings
		:rtype: Boolean, dictionary
		"""
		networkCopy = self.net.copy()

		mappedLinks = {}

		if self.net.node[infra.id].resources['cpu'] <nf.resources['cpu'] or self.net.node[infra.id].resources['mem']<nf.resources['mem'] or self.net.node[infra.id].resources['storage']<nf.resources['storage']:
			return False, mappedLinks
		success, mappedLinks = self.checkLinks(nf,infra,mappedNFs)
		if success:
  			# update the resources
			self.net.node[infra.id].resources['cpu']-=nf.resources['cpu']
			self.net.node[infra.id].resources['mem']-=nf.resources['mem']
			self.net.node[infra.id].resources['storage']-=nf.resources['storage']
		else:
  			# because the checkLinks might change the capacities but the full mapping is not successful
			self.net = networkCopy

		return success, mappedLinks

	def checkLinks(self,nf,infra,mappedNFs):
		"""
		Check if the connected links to a  NF can also be mapped to a path/link
		:param nf: the nf which is checked for the mapped 
		:type nf: Node
		:param infra: the candidate infrastructre node which hosts the nf
		:type infra: Node
		:param mappedNFs: the mapping between NFs and physical nodes
		:type mappedNFs: dictionary
		:return: success of the link mapping and the link mappings
		:rtype: Boolean, dictionary
		"""
  		
		mappedLinks = {}

		bwDictPre={}
		bwDictSuc={}

		neighborsSuc = list(self.selectedDecomp.network.node[id] for id in 
    			self.selectedDecomp.network.successors(nf.id) if 
    			self.selectedDecomp.network.node[id].type == Node.NF) + list(self.selectedDecomp.network.node[id] for id in 
    			self.selectedDecomp.network.successors(nf.id) if 
    			self.selectedDecomp.network.node[id].type == Node.SAP)

		neighborsPre = list(self.selectedDecomp.network.node[id] for id in 
    			self.selectedDecomp.network.predecessors(nf.id) if 
    			self.selectedDecomp.network.node[id].type == Node.NF) + list(self.selectedDecomp.network.node[id] for id in 
    			self.selectedDecomp.network.predecessors(nf.id) if 
    			self.selectedDecomp.network.node[id].type == Node.SAP) 

		for neigh in neighborsPre:
			if (neigh.id,nf.id) in self.requirements0.keys():

				bwDictPre[neigh.id]=self.requirements0[(neigh.id,nf.id)]['bandwidth']
			else:
				bwDictPre[neigh.id]= 0 

		for neigh in neighborsSuc:
			if (nf.id,neigh.id) in self.requirements0.keys():
				bwDictSuc[neigh.id]=self.requirements0[(nf.id,neigh.id)]['bandwidth']
			else:
				bwDictSuc[neigh.id]= 0

		neighborsPre = sorted(neighborsPre, key = lambda node: bwDictPre[node.id], reverse= True)
		neighborsSuc = sorted(neighborsSuc, key = lambda node: bwDictSuc[node.id], reverse= True)
		
		for neigh in neighborsPre:
			if neigh.id in mappedNFs.keys():
				networkCopy = self.net.copy()

				# remove the links between nfs and infra
				for l in list(self.net0.links):
					if (l.src.node in self.net0.nfs and l.dst.node in self.net0.infras) or (l.src.node in self.net0.infras and l.dst.node in self.net0.nfs):
						networkCopy.remove_edge(l.src.node.id,l.dst.node.id)
					

				while True:
					if nx.has_path(networkCopy,mappedNFs[neigh.id],infra.id):
						path = nx.shortest_path(networkCopy,mappedNFs[neigh.id],infra.id)
					else:
						path = None
						break
					networkCopy, success = self.checkBWDelay(path,self.requirements0[(neigh.id,nf.id)]['bandwidth'],self.requirements0[(neigh.id,nf.id)]['delay'],networkCopy)
					if success:
						break
				if path == None:
					return False, mappedLinks
				else:
					mappedLinks[(neigh.id,nf.id)]={'path':path}

					# update the bandwidth of the links
					links = list(self.net0.links)
					for i in range(len(path)-1):
						for l in links:
							if l.src.node.id == path[i] and l.dst.node.id==path[i+1]:
								self.net[path[i]][path[i+1]][l.id].bandwidth-=self.requirements0[(neigh.id,nf.id)]['bandwidth']
								break
		for neigh in neighborsSuc:
			if neigh.id in mappedNFs.keys():
				networkCopy = self.net.copy()

				# remove the links between nfs and infra
				for l in list(self.net0.links):
					if (l.src.node in self.net0.nfs and l.dst.node in self.net0.infras) or l.src.node in self.net0.infras and l.dst.node in self.net0.nfs:
						networkCopy.remove_edge(l.src.node.id,l.dst.node.id)
					

				while True:
					if nx.has_path(networkCopy,infra.id,mappedNFs[neigh.id]):
						path = nx.shortest_path(networkCopy,infra.id,mappedNFs[neigh.id])
					else:
						path=None
						break
					networkCopy, success = self.checkBWDelay(path,self.requirements0[(nf.id,neigh.id)]['bandwidth'],self.requirements0[(nf.id,neigh.id)]['delay'],networkCopy)
					if success:
						break
				if path == None:
					return False, mappedLinks
				else:
					mappedLinks[(nf.id,neigh.id)]={'path':path}
    				# update the bandwidth of the links
					links = list(self.net0.links)
					for i in range(len(path)-1):
						for l in links:
							if l.src.node.id == path[i] and l.dst.node.id==path[i+1]:
								self.net[path[i]][path[i+1]][l.id].bandwidth-=self.requirements0[(nf.id,neigh.id)]['bandwidth']
								break

		return True, mappedLinks

	def checkBWDelay(self, path,bw, delay, network):
		"""
		Check the end to end delay of the path used for mapping a link does not exceed the maximum allowed delay of the link
		Check the available bandwidth of each link along a path is sufficient for mappinf the link
		:param path: the path to map a link in the request to
		:type path: the list of the links in the physical network
		:param bw: the bw requirement of the link the request
		:type bw: int
		:param delay: the maximum allowed delay on the link in the request
		:type delay: float
		:param network: the physical network to check for the mapping
		:type network: networkx
		:return: the updated network and the success of checking
		:rtype: networkx, Boolean
		"""
		EndtoEndDelay = 0
		links = list(self.net0.links)
		for i in range(len(path)-1):
			for l in links:
				if l.src.node.id==path[i] and l.dst.node.id==path[i+1]:
					
					EndtoEndDelay+=self.net[path[i]][path[i+1]][l.id].delay
    				
					if EndtoEndDelay> delay or self.net[path[i]][path[i+1]][l.id].bandwidth<bw:
						network.remove_edge(path[i],path[i+1])
						return network, False
					break

		return network, True  		

	def updateResources(self,nf,infra_id,mappedLinks):
		"""
		update the resources in a network. Release resources
		:param nf: the nf to relase the resources for
		:type nf:Node
		:param infra_id:the id of the infra node to release its resourcess
		:type infra_id: string
		:param mappedLinks: the mapping of links in request to the physcial path/link
		:type mappedLinks:dictionary

		"""

		self.net.node[infra_id].resources['cpu']+=nf.resources['cpu']
		self.net.node[infra_id].resources['mem']+=nf.resources['mem']
		self.net.node[infra_id].resources['storage']+=nf.resources['storage']

		neighborsSuc = list(self.selectedDecomp.network.node[id] for id in 
    			self.selectedDecomp.network.successors(nf.id) if 
    			self.selectedDecomp.network.node[id].type == Node.NF) + list(self.selectedDecomp.network.node[id] for id in 
    			self.selectedDecomp.network.successors(nf.id) if 
    			self.selectedDecomp.network.node[id].type == Node.SAP)
		neighborsPre = list(self.selectedDecomp.network.node[id] for id in 
    			self.selectedDecomp.network.predecessors(nf.id) if 
    			self.selectedDecomp.network.node[id].type == Node.NF) + list(self.selectedDecomp.network.node[id] for id in 
    			self.selectedDecomp.network.predecessors(nf.id) if 
    			self.selectedDecomp.network.node[id].type == Node.SAP)

		links = list(self.net0.links)
		for neigh in neighborsSuc:
			if (nf.id,neigh.id) in mappedLinks.keys():
				path = mappedLinks[(nf.id,neigh.id)]
				if len(path)!=0:
					for i in range(len(path)-1):
						for l in links:
							if l.src.node.id == path[i] and l.dst.node.id==path[i+1]:
								self.net[path[i]][path[i+1]][l.id].bandwidth+=self.requirements0[(nf.id,neigh.id)]['bandwidth']
								break
		for neigh in neighborsPre:
			if (neigh.id,nf.id) in mappedLinks.keys():
				path = mappedLinks[(neigh.id,nf.id)]
				if len(path)!=0:
					for i in range(len(path)-1):
						for l in links:
							if l.src.node.id==path[i] and l.dst.node.id == path[i+1]:
								self.net[path[i]][path[i+1]][l.id].bandwidth+=self.requirements0[(neigh.id,nf.id)]['bandwidth']
								break

	def _addFlowrulesToNFFGDerivatedFromReqLinks (self, v1, v2, reqlid, nffg, mappedNFs, mappedLinks):
		"""
   	 	Adds the flow rules of the path of the request link (v1,v2,reqlid)
    	to the ports of the Infras.
    	The required Port objects are stored in 'infra_ports' field of
    	mappedLinks. Flowrules must be installed to the 'nffg's
    	Ports, NOT self.net!! (Port id-s can be taken from self.net as well)
    	Flowrule format is:
      	match: in_port=<<Infraport id>>;flowclass=<<Flowclass of SGLink if
                     there is one>>;TAG=<<Neighboring VNF ids and linkid>>
      	action: output=<<outbound port id>>;TAG=<<Neighboring VNF ids and
      	linkid>>/UNTAG
    	WARNING: If multiple SGHops starting from a SAP are mapped to paths whose 
    	first infrastructure link is common, starting from the same SAP, the first
    	Infra node can only identify which packet belongs to which SGHop based on 
    	the FLOWCLASS field, which is considered optional.
		"""
		helperlink = mappedLinks[(v1,v2)]
		path = helperlink['path']


		links = list(self.net0.links)

		linkids=[]
		for i in range(len(path)-1):

			for l in links:
				
				if l.src.node.id == path[i] and l.dst.node.id==path[i+1]:
					linkids.append(l.id)

    	
		if 'infra_ports' in helperlink:
			flowsrc = helperlink['infra_ports'][0]
			flowdst = helperlink['infra_ports'][1]
		else:
			flowsrc = None
			flowdst = None

      	
		reqlink = self.selectedDecomp.network[v1][v2][reqlid]
		bw = self.requirements0[(v1,v2)]['bandwidth']
    	# Let's use the substrate SAPs' ID-s for TAG definition.
		if self.selectedDecomp.network.node[v1].type == 'SAP':
			v1 = self.getIdOfChainEnd_fromNetwork(v1,mappedNFs)
		if self.selectedDecomp.network.node[v2].type == 'SAP':
			v2 = self.getIdOfChainEnd_fromNetwork(v2,mappedNFs)
    	# The action and match are the same format
		tag = "TAG=%s|%s|%s" % (v1, v2, reqlid)
		if len(path) == 1:
			
      		# collocation happened, none of helperlink`s port refs should be None
			match_str = "in_port="
			action_str = "output="
			if flowdst is None or flowsrc is None:
				raise uet.InternalAlgorithmException(
          		"No InfraPort found for a dynamic link of collocated VNFs")
			match_str += str(flowsrc.id)
			if reqlink.flowclass is not None:
				match_str += ";flowclass=%s" % reqlink.flowclass
			action_str += str(flowdst.id)
			self.log.debug("Collocated flowrule %s => %s added to Port %s of %s" % (
        			match_str, action_str, flowsrc.id, path[0]))

			flowsrc.add_flowrule(match_str, action_str, bw)
			# added specifically for ER
			for i in self.selectedDecomp.network.node[v1].ports:
				if 'match' in i.properties:
					for j in i.properties['match'].keys():
						flowsrc.add_flowrule(i.properties['match'][j], action_str, bw)

		else:
	

      		# set the flowrules for the transit Infra nodes
			for i, j, k, lidij, lidjk in zip(path[:-2], path[1:-1], path[2:],
                                       linkids[:-1], linkids[1:]):
				match_str = "in_port="
				action_str = "output="
				match_str += str(self.net[i][j][lidij].dst.id)
				if reqlink.flowclass is not None:
					match_str += ";flowclass=%s" % reqlink.flowclass
				action_str += str(self.net[j][k][lidjk].src.id)
        		# Transit SAPs would mess it up pretty much, but it is not allowed.
				if self.net.node[i].type == 'SAP':
					action_str += ";" + tag
				else:
					match_str += ";" + tag
				if self.net.node[k].type == 'SAP':
          			# remove TAG in the last port where flowrules are stored 
          			# if the next node is a SAP
          			# NOTE: If i and k are SAPs but j isn`t, then in j`s port TAG and 
          			# UNTAG action will be present at the same time.
					action_str += ";UNTAG"
				self.log.debug("Transit flowrule %s => %s added to Port %s of %s" % (
          			match_str, action_str, self.net[i][j][lidij].dst.id, j))
				nffg.network[i][j][lidij].dst.add_flowrule(match_str, action_str, bw)

      		# set flowrule for the first element if that is not a SAP
			if nffg.network.node[path[0]].type != 'SAP':
				match_str = "in_port="
				action_str = "output="
				if flowsrc is None:
					raise uet.InternalAlgorithmException(
            		"No InfraPort found for a dynamic link which starts a path")
				match_str += str(flowsrc.id)
				if reqlink.flowclass is not None:
					match_str += ";flowclass=%s" % reqlink.flowclass
				action_str += str(nffg.network[path[0]][path[1]][linkids[0]].src.id)
				action_str += ";" + tag
				self.log.debug("Starting flowrule %s => %s added to Port %s of %s" % (
          			match_str, action_str, flowsrc.id, path[0]))
				flowsrc.add_flowrule(match_str, action_str, bw)

      		# set flowrule for the last element if that is not a SAP


			if nffg.network.node[path[-1]].type != 'SAP':
				
				match_str = "in_port="
				action_str = "output="
				match_str += str(self.net[path[-2]][path[-1]][linkids[-1]].dst.id)
				if reqlink.flowclass is not None:
					match_str += ";flowclass=%s" % reqlink.flowclass
				match_str += ";" + tag
				if flowdst is None:
					raise uet.InternalAlgorithmException(
            		"No InfraPort found for a dynamic link which finishes a path")
				action_str += str(flowdst.id) + ";UNTAG"
				self.log.debug("Finishing flowrule %s => %s added to Port %s of %s" % (
          			match_str, action_str,
          			self.net[path[-2]][path[-1]][linkids[-1]].dst.id, path[-1]))
				nffg.network[path[-2]][path[-1]][linkids[-1]].dst.add_flowrule(
          			match_str, action_str, bw)


  		




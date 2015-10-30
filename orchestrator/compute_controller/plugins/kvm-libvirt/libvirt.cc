#include "libvirt.h"
#include "libvirt_constants.h"

#ifndef ENABLE_KVM_DPDK_IVSHMEM
	virConnectPtr Libvirt::connection = NULL;
#else
	unsigned int Libvirt::next_tcp_port = FIRST_PORT_FOR_MONITOR;
#endif

#ifndef ENABLE_KVM_DPDK_IVSHMEM
void Libvirt::customErrorFunc(void *userdata, virErrorPtr err)
{
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Failure of libvirt library call:");
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "\tCode: %d", err->code);
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "\tDomain: %d", err->domain);
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "\tMessage: %s", err->message);
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "\tLevel: %d", err->level);
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "\tstr1: %s", err->str1);
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "\tstr2: %s", err->str2);
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "\tstr3: %s", err->str3);
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "\tint1: %d", err->int1);
	logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "\tint2: %d", err->int2);
}
#endif

Libvirt::Libvirt()
{
#ifndef ENABLE_KVM_DPDK_IVSHMEM
	virSetErrorFunc(NULL, customErrorFunc);
#endif
}

Libvirt::~Libvirt()
{
#ifndef ENABLE_KVM_DPDK_IVSHMEM
	if(connection != NULL)
		disconnect();
#endif
}

bool Libvirt::isSupported()
{
#ifndef ENABLE_KVM_DPDK_IVSHMEM
	connect();
	
	if(connection == NULL)
		return false;
#endif

	//TODO check if it supported in case of plain QEMU
	return true;
}

#ifndef ENABLE_KVM_DPDK_IVSHMEM
void Libvirt::connect()
{
	if(connection != NULL)
		//The connection is already open
		return;

	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "Connecting to Libvirt ...");
	connection = virConnectOpen("qemu:///system");
	if (connection == NULL) 
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Failed to open connection to qemu:///system");
	else
		logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "Open connection to qemu:///system successfull");
}

void Libvirt::disconnect()
{
	virConnectClose(connection);
	connection = NULL;
}
#endif

#if not defined(ENABLE_KVM_DPDK_IVSHMEM)
bool Libvirt::startNF(StartNFIn sni)
{
	virDomainPtr dom = NULL;
	char domain_name[64];
	const char *xmlconfig = NULL;
	
	string nf_name = sni.getNfName();
	unsigned int n_ports = sni.getNumberOfPorts();
	map<unsigned int,string> ethPortsRequirements = sni.getEthPortsRequirements();
	string uri_image = description->getURI();

	/* Domain name */
	sprintf(domain_name, "%" PRIu64 "_%s", sni.getLsiID(), sni.getNfName().c_str());
		
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "Using Libvirt XML template %s", uri_image.c_str());
	xmlInitParser();

	xmlDocPtr doc;
	xmlXPathContextPtr xpathCtx;
	xmlXPathObjectPtr xpathObj;

	/* Load XML document */
	doc = xmlParseFile(uri_image.c_str());
	if (doc == NULL) {
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Unable to parse file \"%s\"", uri_image.c_str());
		return 0;
	}

	/* xpath evaluation for Libvirt various elements we may want to update */
	xpathCtx = xmlXPathNewContext(doc);
	if(xpathCtx == NULL) {
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Unable to create new XPath context");
		xmlFreeDoc(doc);
		return 0;
	}
	const xmlChar* xpathExpr = BAD_CAST "/domain/devices/interface|/domain/name|/domain/devices/emulator";
	xpathObj = xmlXPathEvalExpression(xpathExpr, xpathCtx);
	if(xpathObj == NULL) {
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Error: unable to evaluate xpath expression \"%s\"", xpathExpr);
		xmlXPathFreeContext(xpathCtx);
		xmlFreeDoc(doc);
		return 0;
	}

	enum E_updates {
		EMULATOR_UPDATED = 0x01,
		DOMAIN_NAME_UPDATED = 0x02,
	};
	uint32_t update_flags = 0;

	xmlNodeSetPtr nodes = xpathObj->nodesetval;
	int size = (nodes) ? nodes->nodeNr : 0;
    logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "xpath return size: %d", size);
	int i;
	for(i = size - 1; i >= 0; i--) {
	  	xmlNodePtr node = nodes->nodeTab[i];

		if (node != NULL) {
			switch (node->type) {
		   		case XML_ELEMENT_NODE:
		   			if (xmlStrcmp(node->name, (xmlChar*)"name") == 0) {
		   				xmlNodeSetContent(node, BAD_CAST domain_name);
		   				update_flags |= DOMAIN_NAME_UPDATED;
		   			}
		   			else if (xmlStrcmp(node->name, (xmlChar*)"emulator") == 0) {
		   				if (QEMU_BIN_PATH) {
		   					xmlNodeSetContent(node, (xmlChar*)QEMU_BIN_PATH);
							update_flags |= EMULATOR_UPDATED;
		   				}
		   			}
		   			else if (xmlStrcmp(node->name, (xmlChar*)"interface") == 0) {
		   				// Currently we just remove any net interface device present in the template and re-create our own
		   				// with the exception of bridged interfaces which are handy for managing the VM.
		   				xmlChar* type = xmlGetProp(node, (xmlChar*)"type");
		   				if (xmlStrcmp(type, (xmlChar*)"bridge") == 0) {
							xmlFree(type);
		   					continue;
		   				}
		   				xmlUnlinkNode(node);
		   				xmlFreeNode(node);
		   			}
		   			break;
		   		case XML_ATTRIBUTE_NODE:
		   			logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "ATTRIBUTE found here");
		   			break;
		   		default:
		   			logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Other type");
		   			break;
		   	}
		}

		/*
		 * All the elements returned by an XPath query are pointers to
		 * elements from the tree *except* namespace nodes where the XPath
		 * semantic is different from the implementation in libxml2 tree.
		 * As a result when a returned node set is freed when
		 * xmlXPathFreeObject() is called, that routine must check the
		 * element type. But node from the returned set may have been removed
		 * by xmlNodeSetContent() resulting in access to freed data.
		 * This can be exercised by running
		 *       valgrind xpath2 test3.xml '//discarded' discarded
		 * There is 2 ways around it:
		 *   - make a copy of the pointers to the nodes from the result set
		 *     then call xmlXPathFreeObject() and then modify the nodes
		 * or
		 *   - remove the reference to the modified nodes from the node set
		 *     as they are processed, if they are not namespace nodes.
		 */
		 if (nodes->nodeTab[i]->type != XML_NAMESPACE_DECL) {
		      nodes->nodeTab[i] = NULL;
		 }
	}

	/* Cleanup of XPath data */
	xmlXPathFreeObject(xpathObj);

    /* Add domain name if not present */
    if (0 == (update_flags & DOMAIN_NAME_UPDATED)) {
		xmlNewTextChild(xmlDocGetRootElement(doc), NULL, BAD_CAST "name", BAD_CAST domain_name);
    }

	/* Create xpath evaluation context for Libvirt domain/devices */
	/* Evaluate xpath expression */
	const xmlChar* xpathExpr_devs = BAD_CAST "/domain/devices";
	xpathObj = xmlXPathEvalExpression(xpathExpr_devs, xpathCtx);
	if(xpathObj == NULL) {
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Error: unable to evaluate xpath expression \"%s\"", xpathExpr);
		xmlXPathFreeContext(xpathCtx);
		xmlFreeDoc(doc);
		return 0;
	}
	nodes = xpathObj->nodesetval;
	if (!nodes || (nodes->nodeNr != 1)) {
		logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "xpath(devices) failed accessing <devices> node");
		xmlXPathFreeContext(xpathCtx);
		xmlFreeDoc(doc);
		return 0;
	}

    xmlNodePtr devices = nodes->nodeTab[0];

    /* Add emulator if not present and must be modified */
    if ((0 == (update_flags & EMULATOR_UPDATED)) && (QEMU_BIN_PATH != NULL)) {
    	xmlNewTextChild(devices, NULL, BAD_CAST "emulator", BAD_CAST QEMU_BIN_PATH);
    }
	
	/* Create XML for VM */
#ifdef ENABLE_KVM_DPDK_USVHOST
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "This function is KVM-USVHOS");

	/* Create NICs */
	for(unsigned int i=1;i<=n_ports;i++) {
		// TODO: This is OVS vhostuser specific - Should be coordinated with network plugin part...
		char sock_path[255];
		sprintf(sock_path, "%s/%s_%u", OVS_BASE_SOCK_PATH, domain_name, i);
		xmlNodePtr ifn = xmlNewChild(devices, NULL, BAD_CAST "interface", NULL);
	    xmlNewProp(ifn, BAD_CAST "type", BAD_CAST "vhostuser");

	    xmlNodePtr srcn = xmlNewChild(ifn, NULL, BAD_CAST "source", NULL);
	    xmlNewProp(srcn, BAD_CAST "type", BAD_CAST "unix");
	    xmlNewProp(srcn, BAD_CAST "path", BAD_CAST sock_path);
	    xmlNewProp(srcn, BAD_CAST "mode", BAD_CAST "client");

	    xmlNodePtr modeln = xmlNewChild(ifn, NULL, BAD_CAST "model", NULL);
	    xmlNewProp(modeln, BAD_CAST "type", BAD_CAST "virtio");

		if(ethPortsRequirements.count(i) > 0) {
    	    xmlNodePtr macn = xmlNewChild(ifn, NULL, BAD_CAST "mac", NULL);
    	    xmlNewProp(macn, BAD_CAST "address", BAD_CAST (ethPortsRequirements.find(i)->second.c_str()));
		}

	    xmlNodePtr drvn = xmlNewChild(ifn, NULL, BAD_CAST "driver", NULL);
	    xmlNodePtr drv_hostn = xmlNewChild(drvn, NULL, BAD_CAST "host", NULL);
	    xmlNewProp(drv_hostn, BAD_CAST "csum", BAD_CAST "off");
	    xmlNewProp(drv_hostn, BAD_CAST "gso", BAD_CAST "off");
	    xmlNodePtr drv_guestn = xmlNewChild(drvn, NULL, BAD_CAST "guest", NULL);
	    xmlNewProp(drv_guestn, BAD_CAST "tso4", BAD_CAST "off");
	    xmlNewProp(drv_guestn, BAD_CAST "tso6", BAD_CAST "off");
	    xmlNewProp(drv_guestn, BAD_CAST "ecn", BAD_CAST "off");
	}
#else
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "This function is a 'standard process' in KVM");

	/* Create NICs */
	for(unsigned int i=1;i<=n_ports;i++) {
		char port_name[64] = "";
		
		/*name of port --> lsiID_nfname_i*/		
		sprintf(port_name, "%" PRIu64 "_%s_%u", sni.getLsiID(), nf_name.c_str(), i);
		
		xmlNodePtr ifn = xmlNewChild(devices, NULL, BAD_CAST "interface", NULL);
	    xmlNewProp(ifn, BAD_CAST "type", BAD_CAST "direct");

	    xmlNodePtr srcn = xmlNewChild(ifn, NULL, BAD_CAST "source", NULL);
	    xmlNewProp(srcn, BAD_CAST "dev", BAD_CAST port_name);
	    xmlNewProp(srcn, BAD_CAST "mode", BAD_CAST "passthrough");

	    xmlNodePtr modeln = xmlNewChild(ifn, NULL, BAD_CAST "model", NULL);
	    xmlNewProp(modeln, BAD_CAST "type", BAD_CAST "virtio");
	    
	    xmlNodePtr virt = xmlNewChild(ifn, NULL, BAD_CAST "virtualport", NULL);
	    xmlNewProp(virt, BAD_CAST "type", BAD_CAST "openvswitch");
	}
#endif

	/* Cleanup of XPath data */
	xmlXPathFreeContext(xpathCtx);

	/* Get resulting document */
	xmlChar* xml_buf; int xml_bufsz;
	xmlDocDumpMemory(doc, &xml_buf, &xml_bufsz);
	xmlconfig = (const char *)xml_buf;

	/* Final XML Cleanup */
	xmlFreeDoc(doc);
	xmlCleanupParser();
	
#ifdef DEBUG_KVM 
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "Dumping XML to %s", domain_name);
	FILE* fp = fopen(domain_name, "w");
	if (fp) {
		fwrite(xmlconfig, 1, strlen(xmlconfig), fp);
		fclose(fp);
	}
#endif

	dom = virDomainCreateXML(connection, xmlconfig, 0);
	if (!dom) {
		virDomainFree(dom);
    		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Domain definition failed");
    		return false;
	}
	
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "Boot guest");
	
	virDomainFree(dom);
	
	return true;
}
#else
bool Libvirt::startNF(StartNFIn sni)
{
	//XXX: Libvirt do not define xml tags to define an ivhsmem device to be attached with the virtual machine.
	//However, it define the <qemu:commandline> tag to provide to libvirt generic strings to be used in the
	//qemu command line. Unfortunately, through this mechanism we got an error when libvirt tries to boot the VM.
	//As a consequence, we decide to directly use the QEMU command line for ivshmem virtual machine. I know, this
	//way the code is dirty, but it seems to be the better (fastest) solution to implement ivhsmem support in the
	//universal node.
	
	//XXX: we ignore all the information written in the xml file, except the path with the VM image
	
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "This function is KVM-IVSHMEM");	
	

	char domain_name[64];	
	string nf_name = sni.getNfName();
	unsigned int n_ports = sni.getNumberOfPorts();
	string uri_image = description->getURI();

	/* Domain name */
	sprintf(domain_name, "%" PRIu64 "_%s", sni.getLsiID(), sni.getNfName().c_str());
		
	//Parse the VM template	
		
	xmlInitParser();
	xmlDocPtr doc;

	/* Load XML document */
	doc = xmlParseFile(uri_image.c_str());
	if (doc == NULL) {
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Unable to parse file \"%s\"", uri_image.c_str());
		return 0;
	}

	char *disk_path = NULL;

	xmlNodePtr root = xmlDocGetRootElement(doc);
	for(xmlNodePtr cur_root_child=root->xmlChildrenNode; cur_root_child!=NULL; cur_root_child=cur_root_child->next) 
	{
		if ((cur_root_child->type == XML_ELEMENT_NODE)&&(!xmlStrcmp(cur_root_child->name, (const xmlChar*)"devices")))
		{
			//We are in the <devices> element			
			xmlNodePtr devices = cur_root_child;
			for(xmlNodePtr device = devices->xmlChildrenNode; device != NULL; device = device->next) 
			{
				if ((device->type == XML_ELEMENT_NODE)&&(!xmlStrcmp(device->name, (const xmlChar*)"disk")))
				{					
					//We are in the <disk> element
					xmlChar* attr_type = xmlGetProp(device, (const xmlChar*)"type");
					xmlChar* attr_device = xmlGetProp(device, (const xmlChar*)"device");
										
					if(strcmp((const char*)attr_type,"file")==0 && strcmp((const char*)attr_device,"disk")==0)
					{						
						xmlNodePtr disk = device;
					
						//we are in the proper disk						
						for(xmlNodePtr indisk = disk->xmlChildrenNode; indisk != NULL; indisk = indisk->next) 
						{
						
							if ((indisk->type == XML_ELEMENT_NODE)&&(!xmlStrcmp(indisk->name, (const xmlChar*)"source")))
							{	
								//We are in the <source> element
								//Retrieve the path of the disk
								xmlChar* attr_file = xmlGetProp(indisk, (const xmlChar*)"file");
								
								disk_path  = (char*)malloc(sizeof(char) * (strlen((const char*)attr_file) + 1));
								memcpy(disk_path, attr_file, strlen((const char*)attr_file));
								disk_path[strlen((const char*)attr_file)] = '\0';					
								goto after_parsing;
							}
						}
						
					}
				}
			}
		}	
		
	}//end iteration over the document
	
after_parsing:
	
	if(disk_path == NULL)
	{
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Wrong XML file describing the VM to run: no path for VM disk found.");
		return false;
	}
	
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "Virtual machine disk available at path: '%s'",disk_path);
	
	
	//Get the command line generator and prepare the command line
	IvshmemCmdLineGenerator cmdgenerator;
	
	
	stringstream ivshmemcmdline;
	for(unsigned int i=1; i <= n_ports; i++)
	{	
		//Retrieve the command line
		
		stringstream portname;;
		portname << "dpdkr" << i;
	
		char cmdline[512];
		if(!cmdgenerator.get_cmdline(portname.str().c_str(), cmdline, 512))
			return false;
			
		ivshmemcmdline << " " << cmdline;
	}
	
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "Command line part for ivshmem '%s'",ivshmemcmdline.str().c_str());
	
	
	stringstream command;
	command << QEMU << " " << nf_name << " " << next_tcp_port << " " << disk_path << "'" << ivshmemcmdline.str().c_str() << "'";
	
	next_tcp_port++; //FIXME: protect with mutex?
	
	int retVal = system(command.str().c_str());
	retVal = retVal >> 8;
	
	if(retVal == 0)
		return false;
		
	return true;
}	
#endif

bool Libvirt::stopNF(StopNFIn sni)
{
#ifndef ENABLE_KVM_DPDK_IVSHMEM
	char *vm_name = new char[64];
	
	/*image_name*/
	sprintf(vm_name, "%" PRIu64 "_%s", sni.getLsiID(), sni.getNfName().c_str());

	assert(connection != NULL);

	/*destroy the VM*/
	if(virDomainDestroy(virDomainLookupByName(connection, vm_name)) != 0){
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "failed to stop (destroy) VM. %s", vm_name);
		return false;
	}
#endif	
	return true;
}

bool Libvirt::interact(string name, string command)
{
	return true;
}


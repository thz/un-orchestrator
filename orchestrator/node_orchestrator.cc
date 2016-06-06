#include "utils/constants.h"
#include "utils/logger.h"
#include "node_resource_manager/rest_server/rest_server.h"

#ifdef ENABLE_DOUBLE_DECKER_CONNECTION
	#include "node_resource_manager/pub_sub/pub_sub.h"
#endif

#ifdef ENABLE_RESOURCE_MANAGER
	#include "node_resource_manager/resource_manager/resource_manager.h"
#endif

#include <unistd.h>
#include <stdlib.h>
#include <string.h>

#include <openssl/sha.h>
#include "node_resource_manager/database_manager/SQLite/SQLiteManager.h"

#include "node_resource_manager/database_manager/SQLite/INIReader.h"

/**
*	Global variables (defined in ../utils/constants.h)
*/
ofp_version_t OFP_VERSION;

/**
*	Private variables
*/
struct MHD_Daemon *http_daemon = NULL;

/*
*
* Pointer to database class
*
*/
SQLiteManager *dbm = NULL;

/**
*	Private prototypes
*/
bool parse_command_line(int argc, char *argv[],int *core_mask,char **config_file, bool *init_db, char **pwd);
bool parse_config_file(char *config_file, int *rest_port, bool *cli_auth, char **nffg_file_name, char **ports_file_name, char **descr_file_name, char **client_name, char **broker_address, char **key_path, bool *orchestrator_in_band, char **un_interface, char **un_address, char **ipsec_certificate);
bool usage(void);
void printUniversalNodeInfo();
bool doChecks(void);
void terminateRestServer(void);
bool createDB(SQLiteManager *dbm, char *pwd);

/**
*	Implementations
*/

void singint_handler(int sig)
{
    logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "The '%s' is terminating...",MODULE_NAME);

	MHD_stop_daemon(http_daemon);
	terminateRestServer();

	if(dbm != NULL)
		dbm->eraseAllToken();

#ifdef ENABLE_DOUBLE_DECKER_CONNECTION
	DoubleDeckerClient::terminate();
#endif

	logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "Bye :D");
	exit(EXIT_SUCCESS);
}

int main(int argc, char *argv[])
{
	//Check for root privileges
	if(geteuid() != 0)
	{
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Root permissions are required to run %s\n",argv[0]);
		exit(EXIT_FAILURE);
	}

	if(!doChecks())
		exit(EXIT_FAILURE);

#ifdef VSWITCH_IMPLEMENTATION_ERFS
	OFP_VERSION = OFP_13;
#else
	OFP_VERSION = OFP_12;
#endif

	int core_mask;
	int rest_port, t_rest_port;
	bool cli_auth, t_cli_auth, orchestrator_in_band, t_orchestrator_in_band, init_db = false;
	char *config_file_name = new char[BUFFER_SIZE];
	char *ports_file_name = new char[BUFFER_SIZE], *t_ports_file_name = NULL;
	char *nffg_file_name = new char[BUFFER_SIZE], *t_nffg_file_name = NULL;
	char *descr_file_name = new char[BUFFER_SIZE], *t_descr_file_name = NULL;
#ifdef ENABLE_DOUBLE_DECKER_CONNECTION
	char *client_name = new char[BUFFER_SIZE];
	char *broker_address = new char[BUFFER_SIZE];
	char *key_path = new char[BUFFER_SIZE];
#endif
	char *t_client_name = NULL, *t_broker_address = NULL, *t_key_path = NULL;
	char *un_interface = new char[BUFFER_SIZE], *t_un_interface = NULL;
	char *un_address = new char[BUFFER_SIZE], *t_un_address = NULL;
	char *ipsec_certificate = new char[BUFFER_SIZE], *t_ipsec_certificate = NULL;
	char *pwd = new char[BUFFER_SIZE];

	string s_un_address;
	string s_ipsec_certificate;

	strcpy(config_file_name, DEFAULT_FILE);

	if(!parse_command_line(argc,argv,&core_mask,&config_file_name,&init_db,&pwd))
		exit(EXIT_FAILURE);

	if(!parse_config_file(config_file_name,&t_rest_port,&t_cli_auth,&t_nffg_file_name,&t_ports_file_name,&t_descr_file_name,&t_client_name,&t_broker_address,&t_key_path,&t_orchestrator_in_band,&t_un_interface,&t_un_address,&t_ipsec_certificate))
		exit(EXIT_FAILURE);

	strcpy(ports_file_name, t_ports_file_name);
	if(strcmp(t_nffg_file_name, "UNKNOWN") != 0)
		strcpy(nffg_file_name, t_nffg_file_name);
	else
		nffg_file_name = NULL;

	if(strcmp(t_descr_file_name, "UNKNOWN") != 0)
		strcpy(descr_file_name, t_descr_file_name);
	else
		descr_file_name = NULL;

#ifdef ENABLE_DOUBLE_DECKER_CONNECTION
	if(strcmp(t_client_name, "UNKNOWN") != 0)
		strcpy(client_name, t_client_name);
	else
		client_name = NULL;

	if(strcmp(t_broker_address, "UNKNOWN") != 0)
		strcpy(broker_address, t_broker_address);
	else
		broker_address = NULL;

	if(strcmp(t_key_path, "UNKNOWN") != 0)
		strcpy(key_path, t_key_path);
	else
		key_path = NULL;
#endif

	if(strcmp(t_un_interface, "UNKNOWN") != 0)
		strcpy(un_interface, t_un_interface);
	else
		un_interface = "";

	if(strcmp(t_un_address, "UNKNOWN") != 0)
		strcpy(un_address, t_un_address);
	else
		un_address = "";

	if(strcmp(t_ipsec_certificate, "UNKNOWN") != 0)
		strcpy(ipsec_certificate, t_ipsec_certificate);
	else
		ipsec_certificate = "";

	rest_port = t_rest_port;
	cli_auth = t_cli_auth;
	orchestrator_in_band = t_orchestrator_in_band;

	if(!string(un_address).empty())
		s_un_address = string(un_address);
	if(!string(ipsec_certificate).empty())
		s_ipsec_certificate = string(ipsec_certificate);

	if(!string(un_address).empty())
	{
		//remove " character from string
		s_un_address.erase(0,1);
		s_un_address.erase(s_un_address.size()-1,1);
	}

	if(!string(ipsec_certificate).empty())
	{
		s_ipsec_certificate.erase(0,1);
		s_ipsec_certificate.erase(s_ipsec_certificate.size()-1,1);
	}

	//test if client authentication is required and if true initialize database
	if(cli_auth)
	{
		//connect to database
		dbm = new SQLiteManager(DB_NAME);
		if(init_db)
		{
			if(!createDB(dbm, pwd))
			{
				logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Database already initialized, argument \"--i\" cannot be specified");
				exit(EXIT_FAILURE);
			}
		}
	}
	else
	{
		if(init_db)
		{
			logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Argument \"--i\" can appear only if authentication is required");
			exit(EXIT_FAILURE);
		}
	}

	//XXX: this code avoids that the program terminates when system() is executed
	sigset_t mask;
	sigfillset(&mask);
	sigprocmask(SIG_SETMASK, &mask, NULL);

#ifdef ENABLE_DOUBLE_DECKER_CONNECTION
	if(!DoubleDeckerClient::init(client_name, broker_address, key_path))
	{
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Cannot start the %s",MODULE_NAME);
		exit(EXIT_FAILURE);
	}
#endif

	if(!RestServer::init(dbm,cli_auth,nffg_file_name,core_mask,ports_file_name,s_un_address,orchestrator_in_band,un_interface,ipsec_certificate))
	{
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Cannot start the %s",MODULE_NAME);
		exit(EXIT_FAILURE);
	}

#ifdef ENABLE_RESOURCE_MANAGER
	ResourceManager::publishDescriptionFromFile(descr_file_name);
#endif

	http_daemon = MHD_start_daemon (MHD_USE_SELECT_INTERNALLY, rest_port, NULL, NULL,&RestServer::answer_to_connection,
		NULL, MHD_OPTION_NOTIFY_COMPLETED, &RestServer::request_completed, NULL,MHD_OPTION_END);

	if (NULL == http_daemon)
	{
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Cannot start the HTTP deamon. The %s cannot be run.",MODULE_NAME);
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Please, check that the TCP port %d is not used (use the command \"netstat -a | grep %d\")",rest_port,rest_port);

		terminateRestServer();

		return EXIT_FAILURE;
	}

	signal(SIGINT,singint_handler);

	printUniversalNodeInfo();
	logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "The '%s' is started!",MODULE_NAME);
	logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "Waiting for commands on TCP port \"%d\"",rest_port);

	rofl::cioloop::get_loop().run();

	return 0;
}

bool parse_command_line(int argc, char *argv[],int *core_mask,char **config_file_name,bool *init_db,char **pwd)
{
	int opt;
	char **argvopt;
	int option_index;

static struct option lgopts[] = {
		{"c", 1, 0, 0},
		{"d", 1, 0, 0},
		{"i", 1, 0, 0},
		{"h", 0, 0, 0},
		{NULL, 0, 0, 0}
	};

	argvopt = argv;
	uint32_t arg_c = 0;

	*core_mask = CORE_MASK;

	while ((opt = getopt_long(argc, argvopt, "", lgopts, &option_index)) != EOF)
    	{
		switch (opt)
		{
			/* long options */
			case 0:
	   			if (!strcmp(lgopts[option_index].name, "c"))/* core mask for network functions */
	   			{
	   				if(arg_c > 0)
	   				{
		   				logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Argument \"--c\" can appear only once in the command line");
	   					return usage();
	   				}
	   				char *port = (char*)malloc(sizeof(char)*(strlen(optarg)+1));
	   				strcpy(port,optarg);

	   				sscanf(port,"%x",&(*core_mask));

	   				arg_c++;
	   			}
				else if (!strcmp(lgopts[option_index].name, "d"))/* inserting configuration file */
	   			{
					if(arg_c > 0)
	   				{
		   				logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Argument \"--d\" can appear only once in the command line");
	   					return usage();
	   				}

	   				strcpy(*config_file_name,optarg);

	   				arg_c++;
	   			}
				else if (!strcmp(lgopts[option_index].name, "i"))/* inserting admin password */
	   			{
					*init_db = true;

					strcpy(*pwd, optarg);

	   				arg_c++;
	   			}
				else if (!strcmp(lgopts[option_index].name, "h"))/* help */
	   			{
	   				return usage();
	   			}
	   			else
	   			{
	   				logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Invalid command line parameter '%s'\n",lgopts[option_index].name);
	   				return usage();
	   			}
				break;
			default:
				return usage();
		}
	}

	return true;
}

bool parse_config_file(char *config_file_name, int *rest_port, bool *cli_auth, char **nffg_file_name, char **ports_file_name, char **descr_file_name, char **client_name, char **broker_address, char **key_path, bool *orchestrator_in_band, char **un_interface, char **un_address, char **ipsec_certificate)
{
	ports_file_name[0] = '\0';
	nffg_file_name[0] = '\0';
	*rest_port = REST_PORT;

	/*
	*
	* Parsing universal node configuration file
	*
	*/
	INIReader reader(config_file_name);

	if (reader.ParseError() < 0) {
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Can't load a default-config.ini file");
		return false;
	}

	/* physical ports file name */
	char *temp_config_file = new char[64];
	strcpy(temp_config_file, (char *)reader.Get("rest server", "configuration_file", "UNKNOWN").c_str());
	if(strcmp(temp_config_file, "UNKNOWN") != 0 && strcmp(temp_config_file, "") != 0)
		*ports_file_name = temp_config_file;
	else
	{
		logger(ORCH_ERROR, MODULE_NAME, __FILE__, __LINE__, "Physical ports file must be present");
		return false;
	}

	/* REST port */
	int temp_rest_port = (int)reader.GetInteger("rest server", "server_port", -1);
	if(temp_rest_port != -1)
		*rest_port = temp_rest_port;

	/* client authentication */
	*cli_auth = reader.GetBoolean("user authentication", "user_authentication", true);

	/* first nf-fg file name */
	char *temp_nf_fg = new char[64];
	strcpy(temp_nf_fg, (char *)reader.Get("rest server", "nf-fg", "UNKNOWN").c_str());
	*nffg_file_name = temp_nf_fg;

	/* description file to export*/
	char *temp_descr = new char[64];
	strcpy(temp_descr, (char *)reader.Get("resource-manager", "description_file", "UNKNOWN").c_str());
	*descr_file_name = temp_descr;
#ifdef ENABLE_DOUBLE_DECKER_CONNECTION
	/* client name of Double Decker */
	char *temp_cli = new char[64];
	strcpy(temp_cli, (char *)reader.Get("double-decker", "client_name", "UNKNOWN").c_str());
	*client_name = temp_cli;

	/* broker address of Double Decker */
	char *temp_dealer = new char[64];
	strcpy(temp_dealer, (char *)reader.Get("double-decker", "broker_address", "UNKNOWN").c_str());
	*broker_address = temp_dealer;

	/* client name of Double Decker */
	char *temp_key = new char[64];
	strcpy(temp_key, (char *)reader.Get("double-decker", "key_path", "UNKNOWN").c_str());
	*key_path = temp_key;
#endif

	/* orchestrator in band or out of band */
	*orchestrator_in_band = reader.GetBoolean("orchestrator", "is_in_band", true);

	/* universal node interface */
	char *temp_ctrl_iface = new char[64];
	strcpy(temp_ctrl_iface, (char *)reader.Get("orchestrator", "un_interface", "UNKNOWN").c_str());
	*un_interface = temp_ctrl_iface;

	/* local ip */
	char *temp_un_address = new char[64];
	strcpy(temp_un_address, (char *)reader.Get("orchestrator", "un_address", "UNKNOWN").c_str());
	*un_address = temp_un_address;

	/* IPsec certificate */
	char *temp_ipsec_certificate = new char[64];
	strcpy(temp_ipsec_certificate, (char *)reader.Get("GRE over IPsec", "certificate", "UNKNOWN").c_str());
	*ipsec_certificate = temp_ipsec_certificate;

	return true;
}

bool createDB(SQLiteManager *dbm, char *pass)
{
	/*
	*
	* Initializing user database
	*
	*/

	unsigned char *hash_token = new unsigned char[HASH_SIZE];
	char *hash_pwd = new char[BUFFER_SIZE];
	char *tmp = new char[HASH_SIZE];
	char *pwd = new char[HASH_SIZE];

	if(dbm->createTable()){
		strcpy(pwd, pass);

		SHA256((const unsigned char*)pwd, sizeof(pwd) - 1, hash_token);

		for (int i = 0; i < HASH_SIZE; i++) {
			sprintf(tmp, "%x", hash_token[i]);
			strcat(hash_pwd, tmp);
	    	}

		dbm->insertUsrPwd("admin", (char *)hash_pwd);

		return true;
	}

	return false;
}

bool usage(void)
{
	stringstream message;

	message << "Usage:                                                                        \n" \
	"  sudo ./name-orchestrator --d configuration_file [options]     						  \n" \
	"                                                                                         \n" \
	"Parameters:                                                                              \n" \
	"  --d configuration_file                                                                 \n" \
	"        File that specifies some parameters such as rest port, physical port file,       \n" \
	"        NF-FG to deploy at the boot, and if client authentication is required            \n" \
	"                                                                                         \n" \
	"Options:                                                                                 \n" \
	"  --c core_mask                                                                           \n" \
	"        Mask that specifies which cores must be used for DPDK network functions. These   \n" \
	"        cores will be allocated to the DPDK network functions in a round robin fashion   \n" \
	"        (default is 0x2)                                                                 \n" \
	"  --i admin_password                                                                     \n" \
	"        Initialize local database and set the password for the default 'admin' user  	  \n" \
	"  --h                                                                                    \n" \
	"        Print this help.                                                                 \n" \
	"                                                                                         \n" \
	"Example:                                                                                 \n" \
	"  sudo ./node-orchestrator --d config/default-config.ini	  							  \n";

	logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "\n\n%s",message.str().c_str());

	return false;
}

/**
*	Prints information about the vSwitch configured and the execution environments supported
*/
void printUniversalNodeInfo()
{

logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "************************************");

#ifdef VSWITCH_IMPLEMENTATION_XDPD
	string vswitch = "xDPd";
#endif
#ifdef VSWITCH_IMPLEMENTATION_OFCONFIG
	string vswitch = "OvS with OFCONFIG protocol";
#endif
#ifdef VSWITCH_IMPLEMENTATION_OVSDB
	stringstream ssvswitch;
	ssvswitch << "OvS with OVSDB protocol";
#ifdef ENABLE_OVSDB_DPDK
	ssvswitch << " (DPDK support enabled)";
#endif
	string vswitch = ssvswitch.str();
#endif
#ifdef VSWITCH_IMPLEMENTATION_ERFS
	string vswitch = "ERFS";
#endif
	logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "* Virtual switch used: '%s'",vswitch.c_str());

	list<string> executionenvironment;
#ifdef ENABLE_KVM
	executionenvironment.push_back("virtual machines");
#endif
#ifdef ENABLE_DOCKER
	executionenvironment.push_back("Docker containers");
#endif
#ifdef ENABLE_DPDK_PROCESSES
	executionenvironment.push_back("DPDK processes");
#endif
#ifdef ENABLE_NATIVE
	executionenvironment.push_back("native functions");
#endif
	logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "* Execution environments supported:");
	for(list<string>::iterator ee = executionenvironment.begin(); ee != executionenvironment.end(); ee++)
		logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "* \t'%s'",ee->c_str());

logger(ORCH_INFO, MODULE_NAME, __FILE__, __LINE__, "************************************");
}

/**
*	This function checks if the UN is properly configured.
*/
bool doChecks(void)
{

#ifdef VSWITCH_IMPLEMENTATION_OFCONFIG
	logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The support to OFCONFIG is deprecated.");
#endif

	return true;
}

void terminateRestServer()
{
	try
	{
		RestServer::terminate();
	}catch(...)
	{
		//Do nothing, since the program is terminating
	}
}

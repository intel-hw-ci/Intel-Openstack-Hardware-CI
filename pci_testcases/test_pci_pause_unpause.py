# Copyright 2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import base64

import netaddr
import testtools

from tempest.api.compute import base
from tempest_lib.common.utils import data_utils
from tempest.common.utils.linux import remote_client
from tempest import config
from tempest import test
from tempest.pci import pci
from tempest.common import waiters
import serial
import time

CONF = config.CONF

class ServersWithSpecificFlavorTestJSON(base.BaseV2ComputeAdminTest):
    run_ssh = CONF.validation.run_validation
    disk_config = 'AUTO'
    @classmethod
    def setup_credentials(cls):
        cls.prepare_instance_network()
        super(ServersWithSpecificFlavorTestJSON, cls).setup_credentials()

    @classmethod
    def setup_clients(cls):
        super(ServersWithSpecificFlavorTestJSON, cls).setup_clients()
        cls.flavor_client = cls.os_adm.flavors_client
        cls.client = cls.servers_client

    @classmethod
    def resource_setup(cls):
        cls.set_validation_resources()

        super(ServersWithSpecificFlavorTestJSON, cls).resource_setup()

    #@testtools.skipIf(not run_ssh, 'Instance validation tests are disabled.')
    @test.attr(type='gate')
    def test_assign_pci_pause_unpause_instance(self):
        pci.get_pci_config(self)
        for info in self.infoList:
            info = info.split(':')
            name = info[0]
            pciid = info[1]

            flavor_with_pci_id = pci.create_flavor_with_extra_specs(self,name)
            admin_pass = self.image_ssh_password

            user_data = pci.gen_user_data("\n".join(pci.SUSPEND_PAUSE_CONSOLE_DATA))

            server_with_pci = (self.create_test_server(
                                      wait_until='ACTIVE',
                                      user_data=user_data,
                                      #personality=personality,
                                      adminPass=admin_pass,
                                      flavor=flavor_with_pci_id))
            
            addresses = self.client.show_server(server_with_pci['id'])['server']
            password = 'cubswin:)'
            
            self.server_id = server_with_pci['id']
            print self.server_id
            print "cubswin:)"
            pci_info = pci.retry_get_pci_output(
                self.client.get_console_output, self.server_id)

            expect_pci = filter(lambda x: pciid in x, pci_info)
            self.assertTrue(not not expect_pci)

            pci_count = len(expect_pci)
            self.assertEqual(1, pci_count)
            
	        #self.server_id = server_with_pci['id']
            #linux_client = remote_client.RemoteClient(addresses,
            #                                      self.ssh_user, password)
            #pci_flag = linux_client.get_pci(pciid)
            #self.assertTrue(pci_flag is not None)
            #pci_count = linux_client.get_pci_count(pciid)
            #pci_count = pci_count.strip()
            #self.assertEqual('1',pci_count)

            self.client.pause_server(self.server_id)
            waiters.wait_for_server_status(self.client, self.server_id, 'PAUSED')
            self.client.unpause_server(self.server_id)
            waiters.wait_for_server_status(self.client, self.server_id, 'ACTIVE')

            cmd = ["sudo", "virsh", "dumpxml", server_with_pci["id"]]
            xml = pci.shell_command(cmd)
            serial_path = pci.get_serial_path(xml)
            cmd = ["sudo", "chmod", "a+wr", serial_path]
            pci.shell_command(cmd)
            ser = serial.Serial(port=serial_path, baudrate=38400, timeout=1)
            for x in range(10):
                ser.write('0\n')
                time.sleep(1)
                str = ser.readall()
                if str.count('2') > 0 :
                    break
            ser.close()
    
            pci_info = pci.retry_get_pci_output(
                self.client.get_console_output, self.server_id,
                DELIMITER="SP LSPCI")

            expect_pci = filter(lambda x: pciid in x, pci_info)
            self.assertTrue(not not expect_pci)

            pci_count = len(expect_pci)
            self.assertEqual(1, pci_count)

            #linux_client = remote_client.RemoteClient(addresses,
            #                                      self.ssh_user, password)
	        #pci_recover_flag = linux_client.get_pci(pciid)
            #self.assertTrue(pci_recover_flag is not None)	
            #pci_count = linux_client.get_pci_count(pciid)
            #pci_count = pci_count.strip()
            #self.assertEqual('1',pci_count)

class ServersWithSpecificFlavorTestXML(ServersWithSpecificFlavorTestJSON):
    _interface = 'xml'

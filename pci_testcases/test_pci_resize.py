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

CONF = config.CONF

class ServersWithSpecificFlavorTestJSON(base.BaseV2ComputeAdminTest):
    run_ssh = CONF.validation.run_validation
    disk_config = 'AUTO'

    @classmethod
    def setUpClass(cls):
        super(ServersWithSpecificFlavorTestJSON, cls).setUpClass()
        cls.meta = {'hello': 'world'}
        cls.accessIPv4 = '1.1.1.1'
        cls.accessIPv6 = '0000:0000:0000:0000:0000:babe:220.12.22.2'
        cls.name = data_utils.rand_name('server')
        file_contents = 'This is a test file.'
        personality = [{'path': '/test.txt',
                       'contents': base64.b64encode(file_contents)}]
        cls.client = cls.servers_client
        cls.flavor_client = cls.os_adm.flavors_client
        cli_resp = cls.create_test_server(name=cls.name,
                                          metadata=cls.meta,
                                          accessIPv4=cls.accessIPv4,
                                          accessIPv6=cls.accessIPv6,
                                          personality=personality,
                                          disk_config=cls.disk_config)

    def _detect_server_image_flavor(self, server_id):
        # Detects the current server image flavor ref.
        resp,server = self.client.get_server(server_id)
        current_flavor = server['flavor']['id']
        new_flavor_ref = self.flavor_ref_alt \
            if current_flavor == self.flavor_ref else self.flavor_ref
        return current_flavor, new_flavor_ref


    #@testtools.skipIf(not run_ssh, 'Instance validation tests are disabled.')
    #@test.skip_because(bug="1368201")
    @test.attr(type='gate')
    def test_assign_pci_resize_instance(self):
	#Get PCI related parameter and ready to test
        pci.get_pci_config(self)
        for info in self.infoList:
            info = info.split(':')
            name = info[0]
            pciid = info[1]
    
            flavor_with_pci_id = pci.create_flavor_with_extra_specs(self,name)
            admin_pass = self.image_ssh_password


            cont = pci.gen_rc_local_dict(pci.RC_LSPCI)
            print cont
            personality = [
                {'path': "/etc/rc.local",
                 'contents': cont}]

            user_data = pci.gen_user_data("\n".join(pci.CONSOLE_DATA))

            server_with_pci = (self.create_test_server(
                                      wait_until='ACTIVE',
                                      user_data=user_data,
                                      personality=personality,
                                      adminPass=admin_pass,
                                      flavor=flavor_with_pci_id))

            addresses = self.client.show_server(server_with_pci['id'])['server']
            password = 'cubswin:)'
            self.server_id = server_with_pci['id']
            self.server_id = server_with_pci['id']
            print "cubswin:)"
            pci_info = pci.retry_get_pci_output(
                self.client.get_console_output, self.server_id)

            expect_pci = filter(lambda x: pciid in x, pci_info)
            self.assertTrue(not not expect_pci)

            pci_count = len(expect_pci)
            self.assertEqual(1, pci_count)


#_            server_with_pci = (self.create_test_server(
#                                      wait_until='ACTIVE',
#                                      adminPass=admin_pass,
#                                      flavor=flavor_with_pci_id))
#
#            addresses = self.client.get_server(server_with_pci['id'])
#            password = 'cubswin:)'
#
#            linux_client = remote_client.RemoteClient(addresses,
#                                                  self.ssh_user, password)
#            pci_flag = linux_client.get_pci(pciid)
#            self.assertTrue(pci_flag is not None)
#	    pci_count = linux_client.get_pci_count(pciid)
#            pci_count = pci_count.strip()
#            self.assertEqual('1',pci_count)
#
	    self.server_id = server_with_pci['id']
            new_flavor_ref = pci.create_flavor_with_extra_specs(self,name,count=2)
            self.client.resize_server(self.server_id, new_flavor_ref)
            #self.assertEqual(202, resp.status)
            waiters.wait_for_server_status(self.client, self.server_id, 'VERIFY_RESIZE')

            self.client.confirm_resize_server(self.server_id)
            waiters.wait_for_server_status(self.client, self.server_id, 'ACTIVE')
            server = self.client.show_server(self.server_id)
            self.assertEqual(new_flavor_ref, server['server']['flavor']['id'])

            pci_info = pci.retry_get_pci_output(
                self.client.get_console_output, self.server_id,
                DELIMITER="RC LSPCI")

            expect_pci = filter(lambda x: pciid in x, pci_info)
            self.assertTrue(not not expect_pci)

            pci_count = len(expect_pci)
            self.assertEqual(2, pci_count)


#	    pci_recover_flag = linux_client.get_pci(pciid)
#            self.assertTrue(pci_recover_flag is not None)
#	    pci_count = linux_client.get_pci_count(pciid)
#            pci_count = pci_count.strip()
#            self.assertEqual('2',pci_count)
#

class ServersWithSpecificFlavorTestXML(ServersWithSpecificFlavorTestJSON):
    _interface = 'xml'

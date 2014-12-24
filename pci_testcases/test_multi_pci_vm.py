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
from tempest.common.utils import data_utils
from tempest.common.utils.linux import remote_client
from tempest import config
from tempest import test
from tempest.pci import pci

CONF = config.CONF

class MultiPCIVmTestJSON(base.BaseV2ComputeAdminTest):
    run_ssh = CONF.compute.run_ssh
    disk_config = 'AUTO'

    @classmethod
    def setUpClass(cls):
        super(MultiPCIVmTestJSON, cls).setUpClass()
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
                                          meta=cls.meta,
                                          accessIPv4=cls.accessIPv4,
                                          accessIPv6=cls.accessIPv6,
                                          personality=personality,
                                          disk_config=cls.disk_config)
        cls.resp, cls.server_initial = cli_resp
        cls.password = cls.server_initial['adminPass']
        cls.client.wait_for_server_status(cls.server_initial['id'], 'ACTIVE')
        resp, cls.server = cls.client.get_server(cls.server_initial['id'])

    @testtools.skipIf(not run_ssh, 'Instance validation tests are disabled.')
    @test.attr(type='gate')
    def test_assign_pci_to_multi_instance(self):
	#Get PCI related parameter and ready to test
        pci.get_pci_config(self)
        for info in self.infoList:
            info = info.split(':')
            name = info[0]
            pciid = info[1]

            flavor_with_pci_id = pci.create_flavor_with_extra_specs(self,name)

            admin_pass = self.image_ssh_password

	    resp, server_with_pci_1 = (self.create_test_server(
                                     wait_until='ACTIVE',
                                     adminPass=admin_pass,
                                     flavor=flavor_with_pci_id))
            resp, server_with_pci_2 = (self.create_test_server(
                                     wait_until='ACTIVE',
                                     adminPass=admin_pass,
                                     flavor=flavor_with_pci_id))
            resp, address = self.client.list_addresses(server_with_pci_1['id'])

            addresses = {'addresses':address}

            password = 'cubswin:)'

            linux_client = remote_client.RemoteClient(addresses,
                                                  self.ssh_user, password)
            pci_flag = linux_client.get_pci(pciid)
            self.assertTrue(pci_flag is not None)

	    pci_count = linux_client.get_pci_count(pciid)
            pci_count = pci_count.strip()
            self.assertEqual('1',pci_count)

	    resp, address2 = self.client.list_addresses(server_with_pci_2['id'])

            addresses2 = {'addresses':address2}

            linux_client2 = remote_client.RemoteClient(addresses2,
                                                  self.ssh_user, password)
            pci_flag_2 = linux_client2.get_pci(pciid)
            self.assertTrue(pci_flag_2 is not None)

	    pci_count2 = linux_client2.get_pci_count(pciid)
            pci_count2 = pci_count2.strip()
            self.assertEqual('1',pci_count2) 



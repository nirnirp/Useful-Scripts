import boto3


class ToggleNATGatewayForDatabricksWorkspaceTrait:
    def __init__(self, profile_name: str, workspace_id: str, region_name: str = 'ap-northeast-1'):
        self.client =  boto3.Session(profile_name=profile_name).client('ec2', region_name=region_name)
        self.vpc_id = self._find_vpc_id_by_name(workspace_id)
        self.route_table = self._find_default_route_table_by_vpcid(self.vpc_id)
        self.subnet_id_for_natgw = self._find_subnet_id_for_natgw_by_vpc_id(self.vpc_id)

    def _find_vpc_id_by_name(self, name:str) -> str:
        response = self.client.describe_vpcs()
        matched_vpcs = []

        for vpc in response['Vpcs']:
            print(f"vpc: {vpc}")
            for tag in vpc.get('Tags', []):
                if tag['Key'] == 'Name' and name in tag['Value']:
                    matched_vpcs.append(vpc)

        if (cnt:= len(matched_vpcs)) != 1:
            raise ValueError(f"{cnt} VPCs found with name '{name}'")
        
        return matched_vpcs[0]['VpcId']

    def _find_default_route_table_by_vpcid(self, vpc_id: str) -> str:
        filter = [
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "association.main", "Values": ["true"]},
        ]
        response = self.client.describe_route_tables(Filters=filter)
        return response["RouteTables"][0]["RouteTableId"]
    
    def _find_subnet_id_for_natgw_by_vpc_id(self, vpc_id: str) -> str:
        filter = [
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
        response = self.client.describe_subnets(Filters=filter)
        matched_subnets = []

        for subnet in response['Subnets']:
            for tag in subnet.get('Tags', []):
                if tag['Key'] == 'Name' and 'nat-gateway-subnet' in tag['Value']:
                    matched_subnets.append(subnet)

        if (cnt:= len(matched_subnets)) != 1:
            raise ValueError(f"{cnt} subnets found with name 'nat-gateway-subnet' in VPC '{vpc_id}'")
        
        return matched_subnets[0]['SubnetId']


class DeleteNATGateway(ToggleNATGatewayForDatabricksWorkspaceTrait):
    def __init__(self, profile_name: str, workspace_id: str, region_name: str = 'ap-northeast-1'):
        super().__init__(profile_name, workspace_id, region_name)
        self.natgw_id = self._find_natgw_id_by_subnet_id()
        self.eip_association_id = self._find_eip_association_id_by_natgw_id()

    def _find_natgw_id_by_subnet_id(self) -> str:
        filter = [
            {"Name": "subnet-id", "Values": [self.subnet_id_for_natgw]},
            {"Name": "state", "Values": ["available"]},
        ]
        response = self.client.describe_nat_gateways(Filters=filter)
        if (cnt:= len(response['NatGateways'])) != 1:
            raise ValueError(f"{cnt} NatGateways found in subnet '{self.subnet_id_for_natgw}'")
        return response['NatGateways'][0]['NatGatewayId']
    
    def _find_eip_association_id_by_natgw_id(self) -> str:
        filter = [
            {"Name": "nat-gateway-id", "Values": [self.natgw_id]},
        ]
        response = self.client.describe_nat_gateways(Filters=filter)
        if (cnt:= len(response['NatGateways'])) != 1:
            raise ValueError(f"{cnt} NatGateways found in subnet '{self.subnet_id_for_natgw}'")
        return response['NatGateways'][0]['NatGatewayAddresses'][0]['AllocationId']

    def delete_route_to_natgw(self):
        response = self.client.delete_route(
            DestinationCidrBlock = '0.0.0.0/0',
            RouteTableId = self.route_table
        )
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(f"Route to NAT Gateway on {self.route_table} deleted successfully")
        else:
            raise ValueError(f"Failed to delete route to NAT Gateway on {self.route_table}\n{response}")
        
    def delete_natgw(self):
        response = self.client.delete_nat_gateway(
            NatGatewayId = self.natgw_id
        )
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(f"NAT Gateway {self.natgw_id} is deleting...")
            waiter = self.client.get_waiter('nat_gateway_deleted')
            waiter.wait(NatGatewayIds=[self.natgw_id])
            print(f"NAT Gateway {self.natgw_id} deleted successfully")
        else:
            raise ValueError(f"Failed to delete NAT Gateway {self.natgw_id}\n{response}")
    
    def release_eip(self):
        response = self.client.release_address(
            AllocationId = self.eip_association_id
        )
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(f"Elastic IP {self.eip_association_id} released successfully")
        else:
            raise ValueError(f"Failed to release Elastic IP {self.eip_association_id}\n{response}")
        
    def run(self):
        self.delete_route_to_natgw()
        self.delete_natgw()
        self.release_eip()


class CreateNATGateway(ToggleNATGatewayForDatabricksWorkspaceTrait):
    def __init__(self, profile_name: str, workspace_id: str, region_name: str = 'ap-northeast-1'):
        super().__init__(profile_name, workspace_id, region_name)

    def create_eip(self) -> str:
        response = self.client.allocate_address(
            Domain = 'vpc'
        )
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(f"Elastic IP {response['AllocationId']} created successfully")
            return response['AllocationId']
        else:
            raise ValueError(f"Failed to create Elastic IP\n{response}")
        
    def create_natgw(self, eip_association_id: str) -> str:
        response = self.client.create_nat_gateway(
            AllocationId = eip_association_id,
            SubnetId = self.subnet_id_for_natgw
        )
        natid = response['NatGateway']['NatGatewayId']
        self.client.get_waiter('nat_gateway_available').wait(NatGatewayIds=[natid])
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(f"NAT Gateway {natid} created successfully")
            return natid
        else:
            raise ValueError(f"Failed to create NAT Gateway\n{response}")
        
    def create_route_to_natgw(self, natgw_id: str):
        response = self.client.create_route(
            DestinationCidrBlock = '0.0.0.0/0',
            GatewayId = natgw_id,
            RouteTableId = self.route_table,
            )
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(f"Route to NAT Gateway {natgw_id} on {self.route_table} created successfully")
        else:
            raise ValueError(f"Failed to create route to NAT Gateway {natgw_id} on {self.route_table}\n{response}")
        
    def run(self):
        eip_association_id = self.create_eip()
        natgw_id = self.create_natgw(eip_association_id)
        self.create_route_to_natgw(natgw_id)

// Usage..
// Outside
from nat_gateway_manager import DeleteNATGateway, CreateNATGateway

# # Delete an existing NAT Gateway
# deleter = DeleteNATGateway(profile_name="aws_user", workspace_id="workspace_id", region_name='us-west-1')
# deleter.run()

# Create a new NAT Gateway
creator = CreateNATGateway(profile_name="aws_user", workspace_id="workspace_id", region_name='us-west-1')
creator.run()

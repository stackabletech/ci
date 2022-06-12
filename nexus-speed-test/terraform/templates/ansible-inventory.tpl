[all:vars]
ansible_user=root

[nodes]
%{ for index, node in nodes ~}
${node.name} ansible_host=${node.ipv4_address}
%{ endfor ~}

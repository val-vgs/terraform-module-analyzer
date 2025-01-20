"""Resource definitions and tag analysis utilities."""

# AWS resources that commonly support tags
TAGGABLE_RESOURCES = {
    # Compute
    'aws_instance', 'aws_launch_template', 'aws_spot_fleet_request', 'aws_placement_group',
    'aws_capacity_reservation', 'aws_ec2_fleet',

    # Containers
    'aws_ecr_repository', 'aws_ecs_cluster', 'aws_ecs_service', 'aws_ecs_task_definition',
    'aws_eks_cluster', 'aws_eks_fargate_profile', 'aws_eks_node_group',

    # Storage
    'aws_s3_bucket', 'aws_ebs_volume', 'aws_efs_file_system', 'aws_fsx_lustre_file_system',
    'aws_fsx_windows_file_system',

    # Database
    'aws_db_instance', 'aws_rds_cluster', 'aws_dynamodb_table', 'aws_elasticache_cluster',
    'aws_redshift_cluster', 'aws_neptune_cluster', 'aws_docdb_cluster',

    # Networking
    'aws_vpc', 'aws_subnet', 'aws_security_group', 'aws_vpc_endpoint', 'aws_lb',
    'aws_vpc_peering_connection', 'aws_vpn_connection', 'aws_vpn_gateway', 'aws_nat_gateway',
    'aws_network_acl', 'aws_route_table',

    # IAM/Security
    'aws_iam_role', 'aws_iam_policy', 'aws_iam_instance_profile', 'aws_iam_user',
    'aws_iam_group', 'aws_kms_key', 'aws_secretsmanager_secret',

    # Monitoring & Management
    'aws_cloudwatch_log_group', 'aws_sns_topic', 'aws_sqs_queue', 'aws_ssm_parameter',
    'aws_cloudtrail', 'aws_config_configuration_recorder',

    # Analytics
    'aws_athena_workgroup', 'aws_emr_cluster', 'aws_glue_crawler', 'aws_glue_job',
    'aws_kinesis_stream', 'aws_kinesis_firehose_delivery_stream',

    # Application Integration
    'aws_mq_broker', 'aws_sfn_state_machine', 'aws_batch_compute_environment',

    # Developer Tools
    'aws_codebuild_project', 'aws_codecommit_repository', 'aws_codepipeline',

    # Machine Learning
    'aws_sagemaker_endpoint', 'aws_sagemaker_model', 'aws_sagemaker_notebook_instance',

    # Migration & Transfer
    'aws_dms_replication_instance', 'aws_transfer_server',

    # Serverless
    'aws_lambda_function', 'aws_apigatewayv2_api', 'aws_apigatewayv2_stage',

    # Elasticsearch/OpenSearch
    'aws_opensearch_domain', 'aws_elasticsearch_domain',

    # Other AWS Services
    'aws_ecr_registry', 'aws_msk_cluster', 'aws_elastic_beanstalk_environment',
    'aws_workspaces_workspace'
}

# Standard required tags for resources
REQUIRED_TAGS = {
    'Name',         # Resource identifier
    'Environment',  # e.g., prod, staging, dev
    'Project',      # Project or application name
    'Owner',        # Team or individual responsible
    'Cost-Center',  # For cost allocation
    'Terraform'     # Indicates resource is managed by Terraform
}

def is_taggable(resource_type: str) -> bool:
    """Check if a resource type supports tags."""
    return resource_type in TAGGABLE_RESOURCES

def get_provider_from_resource(resource_type: str) -> str:
    """Extract provider name from resource type."""
    return resource_type.split('_')[0]

def get_resource_service(resource_type: str) -> str:
    """Extract AWS service name from resource type."""
    parts = resource_type.split('_')
    if len(parts) > 1:
        return parts[1]
    return ''

def get_common_tag_patterns() -> dict:
    """Return common tag patterns and their descriptions."""
    return {
        'var.tags': 'Direct tag variable reference',
        'merge(var.tags, ...)': 'Tag merging pattern',
        'merge(local.common_tags, ...)': 'Common tags merging pattern',
        'merge(module.tags.outputs, ...)': 'Module-based tag merging',
        'local.tags': 'Local tag variable reference'
    }

def suggest_tag_fixes(resource_type: str, current_tags: set, has_tags_var: bool) -> List[str]:
    """Suggest fixes for tag-related issues."""
    suggestions = []
    missing_required = REQUIRED_TAGS - current_tags
    
    if not has_tags_var:
        suggestions.append("Add a 'tags' variable to the module:")
        suggestions.append("""
    variable "tags" {
      description = "Common tags for all resources"
      type        = map(string)
      default     = {}
    }""")
    
    if missing_required:
        suggestions.append(f"Add missing required tags: {', '.join(missing_required)}")
        
    suggestions.append("Ensure tags are properly propagated:")
    suggestions.append("""
    tags = merge(
      var.tags,
      {
        Name = "${var.name_prefix}-example"
      }
    )""")
    
    return suggestions
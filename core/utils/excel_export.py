# core/utils/excel_export.py
import pandas as pd
from django.http import HttpResponse
from django.db.models import QuerySet
from datetime import datetime
import json
from io import BytesIO


def export_to_excel(data, filename=None, sheet_name='Sheet1'):
    """
    Export data to Excel format.
    
    Args:
        data: Can be:
            - List of dictionaries
            - Pandas DataFrame
            - Django QuerySet
            - List of Django model instances
        filename: Output filename (without extension)
        sheet_name: Excel sheet name
        
    Returns:
        HttpResponse with Excel file
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'export_{timestamp}'
    
    if not filename.endswith('.xlsx'):
        filename = f'{filename}.xlsx'
    
    # Convert different data types to DataFrame
    if isinstance(data, QuerySet):
        # Handle QuerySet
        df = queryset_to_dataframe(data)
    elif hasattr(data, '__iter__') and data and hasattr(data[0], '__dict__'):
        # Handle list of model instances
        df = model_instances_to_dataframe(data)
    elif isinstance(data, pd.DataFrame):
        # Already a DataFrame
        df = data
    else:
        # Assume it's a list of dictionaries
        df = pd.DataFrame(data)
    
    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Write to Excel
    with BytesIO() as bio:
        with pd.ExcelWriter(bio, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        response.write(bio.getvalue())
    
    return response


def queryset_to_dataframe(queryset, fields=None):
    """
    Convert Django QuerySet to Pandas DataFrame.
    
    Args:
        queryset: Django QuerySet
        fields: List of field names to include (if None, include all)
        
    Returns:
        Pandas DataFrame
    """
    if not queryset.exists():
        return pd.DataFrame()
    
    # Get model from queryset
    model = queryset.model
    
    # If fields not specified, get all fields
    if fields is None:
        fields = [field.name for field in model._meta.fields]
    
    # Prepare data
    data = []
    for obj in queryset:
        row = {}
        for field in fields:
            value = getattr(obj, field)
            
            # Handle special field types
            if hasattr(value, '__call__'):
                try:
                    value = value()
                except:
                    value = None
            
            # Handle relationships
            elif hasattr(value, 'pk'):
                value = str(value)
            
            # Handle dates and times
            elif hasattr(value, 'strftime'):
                value = value.strftime('%Y-%m-%d %H:%M:%S')
            
            # Handle JSON fields
            elif isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            
            row[field] = value
        
        data.append(row)
    
    return pd.DataFrame(data)


def model_instances_to_dataframe(instances, fields=None):
    """
    Convert list of Django model instances to Pandas DataFrame.
    
    Args:
        instances: List of model instances
        fields: List of field names to include (if None, include all)
        
    Returns:
        Pandas DataFrame
    """
    if not instances:
        return pd.DataFrame()
    
    model = instances[0].__class__
    
    # If fields not specified, get all fields
    if fields is None:
        fields = [field.name for field in model._meta.fields]
    
    # Prepare data
    data = []
    for instance in instances:
        row = {}
        for field in fields:
            value = getattr(instance, field)
            
            # Handle special field types
            if hasattr(value, '__call__'):
                try:
                    value = value()
                except:
                    value = None
            
            # Handle relationships
            elif hasattr(value, 'pk'):
                value = str(value)
            
            # Handle dates and times
            elif hasattr(value, 'strftime'):
                value = value.strftime('%Y-%m-%d %H:%M:%S')
            
            # Handle JSON fields
            elif isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            
            row[field] = value
        
        data.append(row)
    
    return pd.DataFrame(data)


def export_multiple_sheets(data_dict, filename=None):
    """
    Export multiple DataFrames to different Excel sheets.
    
    Args:
        data_dict: Dictionary of {sheet_name: data}
        filename: Output filename
        
    Returns:
        HttpResponse with Excel file
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'export_{timestamp}'
    
    if not filename.endswith('.xlsx'):
        filename = f'{filename}.xlsx'
    
    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Write to Excel
    with BytesIO() as bio:
        with pd.ExcelWriter(bio, engine='openpyxl') as writer:
            for sheet_name, data in data_dict.items():
                # Convert data to DataFrame if needed
                if isinstance(data, QuerySet):
                    df = queryset_to_dataframe(data)
                elif hasattr(data, '__iter__') and data and hasattr(data[0], '__dict__'):
                    df = model_instances_to_dataframe(data)
                elif isinstance(data, pd.DataFrame):
                    df = data
                else:
                    df = pd.DataFrame(data)
                
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        response.write(bio.getvalue())
    
    return response


def export_to_csv(data, filename=None):
    """
    Export data to CSV format.
    
    Args:
        data: Data to export (same formats as export_to_excel)
        filename: Output filename
        
    Returns:
        HttpResponse with CSV file
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'export_{timestamp}'
    
    if not filename.endswith('.csv'):
        filename = f'{filename}.csv'
    
    # Convert to DataFrame
    if isinstance(data, QuerySet):
        df = queryset_to_dataframe(data)
    elif hasattr(data, '__iter__') and data and hasattr(data[0], '__dict__'):
        df = model_instances_to_dataframe(data)
    elif isinstance(data, pd.DataFrame):
        df = data
    else:
        df = pd.DataFrame(data)
    
    # Create response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Write CSV
    response.write(df.to_csv(index=False))
    
    return response
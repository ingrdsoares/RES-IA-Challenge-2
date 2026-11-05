import json
import re
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE


def stringify(value):
    return json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else value


def csv_safe(value):
    value=stringify(value)
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')):
        return "'"+value
    return value


def write_excel(path, tables, images=None):
    wb=Workbook(); wb.remove(wb.active)
    fragments=[]
    for name,rows in tables.items():
        sheet=wb.create_sheet(name[:31])
        headers=list(dict.fromkeys(key for row in rows for key in row)) if rows else ['status']
        sheet.append(headers)
        for index,row in enumerate(rows,2):
            for col,key in enumerate(headers,1):
                value=stringify(row.get(key))
                if isinstance(value,str):
                    # Preserve raw strings, including XML controls, in numbered fragments.
                    if len(value)>32767 or ILLEGAL_CHARACTERS_RE.search(value):
                        original=value
                        encoded=bool(ILLEGAL_CHARACTERS_RE.search(original))
                        value=json.dumps(original,ensure_ascii=False) if encoded else original
                        for part,offset in enumerate(range(0,len(value),30000),1):
                            fragments.append({'row':f'{name}:{index}','field':key,'part':part,'text':value[offset:offset+30000],'encoding':'json' if encoded else 'plain'})
                        value=f'[Textos: {name}:{index}/{key}]'
                    cell=sheet.cell(index,col,value)
                    cell.data_type='s'
                else:
                    sheet.cell(index,col,value)
        sheet.freeze_panes='A2'; sheet.auto_filter.ref=sheet.dimensions
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width=min(60,max(15,len(str(column[0].value))+2))
    if fragments:
        sheet=wb.create_sheet('Textos')
        sheet.append(['row','field','part','text','encoding'])
        for row in fragments:
            sheet.append(list(row.values()))
            sheet.cell(sheet.max_row,4).data_type='s'
    if images:
        from openpyxl.drawing.image import Image
        sheet=wb.create_sheet('Gráficos')
        for i,image in enumerate(images):
            img=Image(image); img.width=640; img.height=400
            sheet.add_image(img,f'A{1+i*24}')
    wb.save(path)

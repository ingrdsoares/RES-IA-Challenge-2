import io
import zipfile
import pytest

from backend.crawler.esquemas import parse_package, ingest


XSD = b'''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:test">
<xs:include schemaLocation="tipos.xsd"/>
<xs:element name="Nota" type="TNota"/>
<xs:complexType name="TNota"><xs:sequence>
<xs:element name="codigo" type="xs:string" minOccurs="0" maxOccurs="unbounded"><xs:annotation><xs:documentation>Codigo do item</xs:documentation></xs:annotation></xs:element>
</xs:sequence><xs:attribute name="versao" type="xs:string" use="required"/></xs:complexType>
<xs:simpleType name="Regime"><xs:restriction base="xs:string"><xs:enumeration value="MEI"/><xs:pattern value="[A-Z]+"/></xs:restriction></xs:simpleType>
</xs:schema>'''


def package(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for name,raw in files.items():z.writestr(name,raw)
    return stream.getvalue()


def test_catalog_preserves_types_occurrences_facets_and_missing_dependencies():
    docs=parse_package(package({'1.00/nota.xsd':XSD,'1.01/nota.xsd':XSD}))
    assert len(docs)==2
    assert docs[0]['arquivo']!=docs[1]['arquivo']
    doc=docs[0]
    assert doc['target_namespace']=='urn:test'
    code=next(d for d in doc['declaracoes'] if d.get('name')=='codigo')
    assert code['minOccurs']=='0' and code['maxOccurs']=='unbounded'
    assert code['type']=='xs:string' and code['documentacao']=='Codigo do item'
    assert any(d.get('value')=='MEI' for d in doc['declaracoes'])
    assert any(d.get('value')=='[A-Z]+' for d in doc['declaracoes'])
    assert doc['dependencias'][0]['presente_no_pacote'] is False


@pytest.mark.parametrize('name',['../escape.xsd','/absolute.xsd','C:/escape.xsd'])
def test_rejects_unsafe_paths(name):
    with pytest.raises(ValueError):parse_package(package({name:XSD}))


def test_rejects_entities_and_non_schema_xml():
    for raw in [b'<html/>', b'<!DOCTYPE schema [<!ENTITY x "boom">]><schema>&x;</schema>']:
        with pytest.raises(ValueError):parse_package(package({'nota.xsd':raw}))


def test_rejects_empty_package_and_html():
    for raw in [b'<html>erro</html>',package({'readme.txt':b'no schemas'})]:
        with pytest.raises(ValueError):parse_package(raw)


def test_package_snapshot_keeps_zip_and_markdown_and_repeats(tmp_path):
    raw=package({'nota.xsd':XSD})
    info={'title':'Schemas de teste','url':'https://example.test/a.zip','catalog_url':'https://example.test','identity_namespace':'urn:test'}
    path=ingest('teste',info,raw,tmp_path)
    assert (path.parent/'original.zip').read_bytes()==raw
    text=path.read_text(encoding='utf-8')
    assert 'codigo' in text and 'unbounded' in text and 'MEI' in text
    assert 'tipos.xsd' in text
    before=path.read_bytes()
    assert ingest('teste',info,raw,tmp_path)==path
    assert path.read_bytes()==before


def test_wrong_namespace_is_not_published(tmp_path):
    info={'title':'Schemas','url':'https://example.test/a.zip','catalog_url':'https://example.test','identity_namespace':'urn:other'}
    with pytest.raises(ValueError):ingest('teste',info,package({'nota.xsd':XSD}),tmp_path)
    assert list(tmp_path.iterdir())==[]


def test_reports_dependency_inside_package_as_present():
    docs=parse_package(package({'p/nota.xsd':XSD,'p/tipos.xsd':b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>'}))
    doc=next(d for d in docs if d['arquivo']=='p/nota.xsd')
    assert doc['dependencias'][0]['presente_no_pacote'] is True


def test_rejects_archive_above_uncompressed_limit(monkeypatch):
    import backend.crawler.esquemas as schemas
    monkeypatch.setattr(schemas,'MAX_TOTAL',10)
    with pytest.raises(ValueError,match='limites'):
        parse_package(package({'nota.xsd':XSD}))


def test_rejects_individual_schema_above_limit(monkeypatch):
    import backend.crawler.esquemas as schemas
    monkeypatch.setattr(schemas,'MAX_XSD',10)
    with pytest.raises(ValueError,match='individual'):
        parse_package(package({'nota.xsd':XSD}))


def test_unused_dtd_can_be_ignored_without_resolving_entities():
    dtd=b'<!DOCTYPE xs:schema SYSTEM "https://example.invalid/schema.dtd" [<!ENTITY unused "not-expanded">]>'
    docs=parse_package(package({'nota.xsd':dtd+XSD}))
    assert docs[0]['dtd_ignorada'] is True
    assert any(d.get('name')=='Nota' for d in docs[0]['declaracoes'])


def test_used_entity_remains_rejected_after_dtd_removal():
    dtd=b'<!DOCTYPE xs:schema [<!ENTITY external SYSTEM "file:///sensitive">]>'
    raw=dtd+XSD.replace(b'Codigo do item',b'&external;')
    with pytest.raises(ValueError):parse_package(package({'nota.xsd':raw}))

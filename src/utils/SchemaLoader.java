package utils;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONArray;
import com.alibaba.fastjson.JSONObject;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import org.apache.calcite.jdbc.JavaTypeFactoryImpl;
import org.apache.calcite.rel.type.RelDataType;
import org.apache.calcite.rel.type.RelDataTypeFactory;
import org.apache.calcite.schema.SchemaPlus;
import org.apache.calcite.schema.impl.AbstractTable;
import org.apache.calcite.sql.type.SqlTypeName;
import org.apache.calcite.tools.Frameworks;

public final class SchemaLoader {
  private static final String DEFAULT_SCHEMA_NAME = "APP";

  private SchemaLoader() {}

  public static JSONArray load(String dbId) throws Exception {
    String path = "schemas/" + dbId + ".json";
    String text = Files.readString(Paths.get(path), StandardCharsets.UTF_8);
    return JSON.parseArray(text);
  }

  public static String defaultSchemaName() {
    return DEFAULT_SCHEMA_NAME;
  }

  public static SchemaPlus buildSchema(JSONArray schemaJson) {
    SchemaPlus root = Frameworks.createRootSchema(true);
    SchemaPlus app = root.add(DEFAULT_SCHEMA_NAME, new org.apache.calcite.schema.impl.AbstractSchema());

    for (Object item : schemaJson) {
      if (!(item instanceof JSONObject)) {
        throw new IllegalArgumentException("Schema entries must be objects");
      }
      JSONObject tableObj = (JSONObject) item;
      String tableName = firstNonEmpty(
          tableObj.getString("table_name"),
          tableObj.getString("table"),
          tableObj.getString("name"));
      if (tableName == null) {
        throw new IllegalArgumentException("Missing table name in schema entry: " + tableObj);
      }

      JSONArray columns = tableObj.getJSONArray("columns");
      if (columns == null) {
        columns = tableObj.getJSONArray("cols");
      }
      if (columns == null || columns.isEmpty()) {
        throw new IllegalArgumentException("Missing columns for table: " + tableName);
      }

      List<String> colNames = new ArrayList<>();
      List<SqlTypeName> colTypes = new ArrayList<>();
      for (Object colObjRaw : columns) {
        if (!(colObjRaw instanceof JSONObject)) {
          throw new IllegalArgumentException("Column entries must be objects: " + colObjRaw);
        }
        JSONObject colObj = (JSONObject) colObjRaw;
        String colName = firstNonEmpty(
            colObj.getString("name"),
            colObj.getString("column_name"),
            colObj.getString("field"));
        if (colName == null) {
          throw new IllegalArgumentException("Missing column name in table: " + tableName);
        }
        String typeName = firstNonEmpty(
            colObj.getString("type"),
            colObj.getString("data_type"),
            "VARCHAR");
        colNames.add(colName);
        colTypes.add(resolveType(typeName));
      }

      app.add(tableName, new JsonTable(colNames, colTypes));
    }

    return root;
  }

  private static String firstNonEmpty(String... values) {
    for (String value : values) {
      if (value != null && !value.trim().isEmpty()) {
        return value.trim();
      }
    }
    return null;
  }

  private static SqlTypeName resolveType(String raw) {
    String t = raw.trim().toUpperCase();
    if (t.contains("BIGINT")) {
      return SqlTypeName.BIGINT;
    }
    if (t.contains("INT")) {
      return SqlTypeName.INTEGER;
    }
    if (t.contains("DOUBLE") || t.contains("FLOAT") || t.contains("REAL")) {
      return SqlTypeName.DOUBLE;
    }
    if (t.contains("DECIMAL") || t.contains("NUMERIC")) {
      return SqlTypeName.DECIMAL;
    }
    if (t.contains("DATE")) {
      return SqlTypeName.DATE;
    }
    if (t.contains("TIME")) {
      return SqlTypeName.TIME;
    }
    if (t.contains("TIMESTAMP")) {
      return SqlTypeName.TIMESTAMP;
    }
    if (t.contains("BOOL")) {
      return SqlTypeName.BOOLEAN;
    }
    return SqlTypeName.VARCHAR;
  }

  private static final class JsonTable extends AbstractTable {
    private final List<String> columnNames;
    private final List<SqlTypeName> columnTypes;

    private JsonTable(List<String> columnNames, List<SqlTypeName> columnTypes) {
      this.columnNames = columnNames;
      this.columnTypes = columnTypes;
    }

    @Override
    public RelDataType getRowType(RelDataTypeFactory typeFactory) {
      RelDataTypeFactory.Builder builder = new JavaTypeFactoryImpl().builder();
      for (int i = 0; i < columnNames.size(); i++) {
        builder.add(columnNames.get(i), columnTypes.get(i));
      }
      return builder.build();
    }
  }
}

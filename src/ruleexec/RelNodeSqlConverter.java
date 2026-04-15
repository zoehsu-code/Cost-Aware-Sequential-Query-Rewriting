package ruleexec;

import org.apache.calcite.rel.RelNode;
import org.apache.calcite.rel.rel2sql.RelToSqlConverter;
import org.apache.calcite.sql.SqlDialect;
import org.apache.calcite.sql.SqlNode;
import org.apache.calcite.sql.dialect.AnsiSqlDialect;

public final class RelNodeSqlConverter {
  private static final SqlDialect DIALECT = AnsiSqlDialect.DEFAULT;

  private RelNodeSqlConverter() {}

  public static String toSql(RelNode relNode) {
    RelToSqlConverter converter = new RelToSqlConverter(DIALECT);
    SqlNode sqlNode = converter.visitRoot(relNode).asStatement();
    return sqlNode.toSqlString(DIALECT).getSql();
  }
}

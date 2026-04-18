package ruleexec;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONArray;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import org.apache.calcite.DataContexts;
import org.apache.calcite.plan.RelOptRule;
import org.apache.calcite.plan.RelOptUtil;
import org.apache.calcite.plan.hep.HepMatchOrder;
import org.apache.calcite.plan.hep.HepPlanner;
import org.apache.calcite.plan.hep.HepProgramBuilder;
import org.apache.calcite.rel.RelNode;
import org.apache.calcite.rel.RelRoot;
import org.apache.calcite.schema.SchemaPlus;
import org.apache.calcite.sql.SqlNode;
import org.apache.calcite.sql.parser.SqlParser.Config;
import org.apache.calcite.sql.parser.SqlParser;
import org.apache.calcite.rex.RexExecutorImpl;
import org.apache.calcite.tools.FrameworkConfig;
import org.apache.calcite.tools.Frameworks;
import org.apache.calcite.tools.Planner;
import utils.SchemaLoader;

public final class SingleRuleRewriterMain {
  private SingleRuleRewriterMain() {}

  public static void main(String[] args) {
    try {
      String input = readAllStdin();
      JSONArray request = JSON.parseArray(input);
      if (request == null || request.size() != 3) {
        throw new IllegalArgumentException("Input must be JSON array: [db_id, sql, rule_name]");
      }
      if (!(request.get(0) instanceof String)
          || !(request.get(1) instanceof String)
          || !(request.get(2) instanceof String)) {
        throw new IllegalArgumentException("Input types must be [string, string, string]");
      }

      String dbId = request.getString(0);
      String sql = request.getString(1);
      String ruleName = request.getString(2);

      JSONArray schema = SchemaLoader.load(dbId);
      SchemaPlus rootSchema = SchemaLoader.buildSchema(schema);

      RelNode before = sqlToRel(rootSchema, sql);
      RelOptRule rule = RuleRegistry.getRule(ruleName);

      HepProgramBuilder builder = new HepProgramBuilder();
      builder.addRuleInstance(rule);
      builder.addMatchOrder(HepMatchOrder.TOP_DOWN);

      HepPlanner planner = new HepPlanner(builder.build());
      planner.setExecutor(new RexExecutorImpl(DataContexts.EMPTY));
      planner.setRoot(before);
      RelNode after = planner.findBestExp();

      String beforePlan = RelOptUtil.toString(before);
      String afterPlan = RelOptUtil.toString(after);
      debugPlans(ruleName, beforePlan, afterPlan);

      if (beforePlan.equals(afterPlan)) {
        System.out.print(sql);
        return;
      }

      String rewrittenSql = RelNodeSqlConverter.toSql(after);
      System.out.print(rewrittenSql);
    } catch (Exception ex) {
      String message = ex.getMessage() == null ? ex.toString() : ex.getMessage();
      System.err.println(message);
      String debug = System.getenv("SINGLE_RULE_DEBUG");
      if ("1".equals(debug) || "true".equalsIgnoreCase(debug)) {
        ex.printStackTrace(System.err);
      }
      System.exit(1);
    }
  }

  private static RelNode sqlToRel(SchemaPlus rootSchema, String sql) throws Exception {
    Config parserConfig = SqlParser.configBuilder()
        .setCaseSensitive(false)
        .build();
    FrameworkConfig config = Frameworks.newConfigBuilder()
        .defaultSchema(rootSchema.getSubSchema(SchemaLoader.defaultSchemaName()))
        .parserConfig(parserConfig)
        .build();

    Planner planner = Frameworks.getPlanner(config);
    SqlNode parsed = planner.parse(sql);
    SqlNode validated = planner.validate(parsed);
    RelRoot relRoot = planner.rel(validated);
    return relRoot.rel;
  }

  private static String readAllStdin() throws Exception {
    StringBuilder builder = new StringBuilder();
    try (BufferedReader reader =
        new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
      String line;
      while ((line = reader.readLine()) != null) {
        builder.append(line);
      }
    }
    return builder.toString().trim();
  }

  private static void debugPlans(String ruleName, String beforePlan, String afterPlan) {
    String debug = System.getenv("SINGLE_RULE_DEBUG");
    if (!"1".equals(debug) && !"true".equalsIgnoreCase(debug)) {
      return;
    }
    System.err.println("=== SINGLE RULE DEBUG ===");
    System.err.println("rule: " + ruleName);
    System.err.println("--- before plan ---");
    System.err.println(beforePlan);
    System.err.println("--- after plan ---");
    System.err.println(afterPlan);
    System.err.println("plan_changed: " + !beforePlan.equals(afterPlan));
  }
}

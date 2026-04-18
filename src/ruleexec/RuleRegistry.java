package ruleexec;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import org.apache.calcite.plan.RelOptRule;

public final class RuleRegistry {
  private static final String CORE_RULES = "org.apache.calcite.rel.rules.CoreRules";
  private static final String PRUNE_EMPTY_RULES = "org.apache.calcite.rel.rules.PruneEmptyRules";

  private static final Map<String, RelOptRule> RULE_MAP = new LinkedHashMap<>();
  private static final Map<String, String> UNAVAILABLE_RULES = new LinkedHashMap<>();

  static {
    // rule_agg
    register("AGGREGATE_EXPAND_DISTINCT_AGGREGATES", CORE_RULES, "AGGREGATE_EXPAND_DISTINCT_AGGREGATES");
    register("AGGREGATE_EXPAND_DISTINCT_AGGREGATES_TO_JOIN", CORE_RULES, "AGGREGATE_EXPAND_DISTINCT_AGGREGATES_TO_JOIN");
    register("AGGREGATE_JOIN_TRANSPOSE_EXTENDED", CORE_RULES, "AGGREGATE_JOIN_TRANSPOSE_EXTENDED");
    register("AGGREGATE_PROJECT_MERGE", CORE_RULES, "AGGREGATE_PROJECT_MERGE");
    register("AGGREGATE_ANY_PULL_UP_CONSTANTS", CORE_RULES, "AGGREGATE_ANY_PULL_UP_CONSTANTS");
    register("AGGREGATE_UNION_AGGREGATE", CORE_RULES, "AGGREGATE_UNION_AGGREGATE");
    register("AGGREGATE_UNION_TRANSPOSE", CORE_RULES, "AGGREGATE_UNION_TRANSPOSE");
    register("AGGREGATE_VALUES", CORE_RULES, "AGGREGATE_VALUES");
    register("AGGREGATE_INSTANCE", CORE_RULES, "AGGREGATE_INSTANCE");

    // rule_filter
    register("FILTER_AGGREGATE_TRANSPOSE", CORE_RULES, "FILTER_AGGREGATE_TRANSPOSE");
    register("FILTER_CORRELATE", CORE_RULES, "FILTER_CORRELATE");
    register("FILTER_INTO_JOIN", CORE_RULES, "FILTER_INTO_JOIN");
    register("JOIN_CONDITION_PUSH", CORE_RULES, "JOIN_CONDITION_PUSH");
    register("FILTER_MERGE", CORE_RULES, "FILTER_MERGE");
    register("FILTER_MULTI_JOIN_MERGE", CORE_RULES, "FILTER_MULTI_JOIN_MERGE");
    register("FILTER_PROJECT_TRANSPOSE", CORE_RULES, "FILTER_PROJECT_TRANSPOSE");
    register("FILTER_SET_OP_TRANSPOSE", CORE_RULES, "FILTER_SET_OP_TRANSPOSE");
    register("FILTER_TABLE_FUNCTION_TRANSPOSE", CORE_RULES, "FILTER_TABLE_FUNCTION_TRANSPOSE");
    register("FILTER_SCAN", CORE_RULES, "FILTER_SCAN");
    register("FILTER_REDUCE_EXPRESSIONS", CORE_RULES, "FILTER_REDUCE_EXPRESSIONS");
    register("PROJECT_REDUCE_EXPRESSIONS", CORE_RULES, "PROJECT_REDUCE_EXPRESSIONS");
    register("FILTER_INSTANCE", CORE_RULES, "FILTER_INSTANCE");

    // rule_join
    register("JOIN_EXTRACT_FILTER", CORE_RULES, "JOIN_EXTRACT_FILTER");
    register("JOIN_PROJECT_BOTH_TRANSPOSE", CORE_RULES, "JOIN_PROJECT_BOTH_TRANSPOSE");
    register("JOIN_PROJECT_LEFT_TRANSPOSE", CORE_RULES, "JOIN_PROJECT_LEFT_TRANSPOSE");
    register("JOIN_PROJECT_RIGHT_TRANSPOSE", CORE_RULES, "JOIN_PROJECT_RIGHT_TRANSPOSE");
    register("JOIN_LEFT_UNION_TRANSPOSE", CORE_RULES, "JOIN_LEFT_UNION_TRANSPOSE");
    register("JOIN_RIGHT_UNION_TRANSPOSE", CORE_RULES, "JOIN_RIGHT_UNION_TRANSPOSE");
    register("SEMI_JOIN_REMOVE", CORE_RULES, "SEMI_JOIN_REMOVE");
    register("JOIN_REDUCE_EXPRESSIONS", CORE_RULES, "JOIN_REDUCE_EXPRESSIONS");
    register("JOIN_LEFT_INSTANCE", CORE_RULES, "JOIN_LEFT_INSTANCE");
    register("JOIN_RIGHT_INSTANCE", CORE_RULES, "JOIN_RIGHT_INSTANCE");

    // rule_project
    register("PROJECT_CALC_MERGE", CORE_RULES, "PROJECT_CALC_MERGE");
    register("PROJECT_CORRELATE_TRANSPOSE", CORE_RULES, "PROJECT_CORRELATE_TRANSPOSE");
    register("PROJECT_MERGE", CORE_RULES, "PROJECT_MERGE");
    register("PROJECT_MULTI_JOIN_MERGE", CORE_RULES, "PROJECT_MULTI_JOIN_MERGE");
    register("PROJECT_REMOVE", CORE_RULES, "PROJECT_REMOVE");
    register("PROJECT_TO_CALC", CORE_RULES, "PROJECT_TO_CALC");
    register("PROJECT_SUB_QUERY_TO_CORRELATE", CORE_RULES, "PROJECT_SUB_QUERY_TO_CORRELATE");
    register("PROJECT_REDUCE_EXPRESSIONS", CORE_RULES, "PROJECT_REDUCE_EXPRESSIONS");
    register("PROJECT_INSTANCE", CORE_RULES, "PROJECT_INSTANCE");

    // rule_cal
    register("CALC_MERGE", CORE_RULES, "CALC_MERGE");
    register("CALC_REMOVE", CORE_RULES, "CALC_REMOVE");

    // rule_orderby
    register("SORT_JOIN_TRANSPOSE", CORE_RULES, "SORT_JOIN_TRANSPOSE");
    register("SORT_PROJECT_TRANSPOSE", CORE_RULES, "SORT_PROJECT_TRANSPOSE");
    register("SORT_UNION_TRANSPOSE", CORE_RULES, "SORT_UNION_TRANSPOSE");
    register("SORT_REMOVE_CONSTANT_KEYS", CORE_RULES, "SORT_REMOVE_CONSTANT_KEYS");
    register("SORT_REMOVE", CORE_RULES, "SORT_REMOVE");
    register("SORT_INSTANCE", CORE_RULES, "SORT_INSTANCE");
    register("SORT_FETCH_ZERO_INSTANCE", CORE_RULES, "SORT_FETCH_ZERO_INSTANCE");

    // rule_union
    register("UNION_MERGE", CORE_RULES, "UNION_MERGE");
    register("UNION_REMOVE", CORE_RULES, "UNION_REMOVE");
    register("UNION_TO_DISTINCT", CORE_RULES, "UNION_TO_DISTINCT");
    register("UNION_PULL_UP_CONSTANTS", CORE_RULES, "UNION_PULL_UP_CONSTANTS");
    register("UNION_INSTANCE", CORE_RULES, "UNION_INSTANCE");
    register("INTERSECT_INSTANCE", CORE_RULES, "INTERSECT_INSTANCE");
    register("MINUS_INSTANCE", CORE_RULES, "MINUS_INSTANCE");

    // Optional fallback holder for versions that move fields out of CoreRules.
    reRegisterMissingFrom(PRUNE_EMPTY_RULES);
  }

  private RuleRegistry() {}

  private static void register(String externalName, String ownerClassName, String fieldName) {
    RelOptRule rule = resolve(ownerClassName, fieldName);
    if (rule == null) {
      UNAVAILABLE_RULES.put(externalName, ownerClassName + "." + fieldName);
      return;
    }
    RULE_MAP.put(externalName, rule);
  }

  private static void reRegisterMissingFrom(String ownerClassName) {
    Set<String> missing = new LinkedHashSet<>(UNAVAILABLE_RULES.keySet());
    for (String name : missing) {
      RelOptRule rule = resolve(ownerClassName, name);
      if (rule != null) {
        RULE_MAP.put(name, rule);
        UNAVAILABLE_RULES.remove(name);
      }
    }
  }

  private static RelOptRule resolve(String ownerClassName, String fieldName) {
    try {
      Class<?> holder = Class.forName(ownerClassName);
      Object value = holder.getField(fieldName).get(null);
      if (value instanceof RelOptRule) {
        return (RelOptRule) value;
      }
      return null;
    } catch (ReflectiveOperationException | LinkageError ex) {
      return null;
    }
  }

  public static RelOptRule getRule(String name) {
    RelOptRule rule = RULE_MAP.get(name);
    if (rule != null) {
      return rule;
    }
    String unavailable = UNAVAILABLE_RULES.get(name);
    if (unavailable != null) {
      throw new IllegalArgumentException(
          "Rule exists in registry list but is unavailable in current Calcite: " + name + " -> " + unavailable);
    }
    throw new IllegalArgumentException("Unsupported rule: " + name);
  }

  public static boolean contains(String name) {
    return RULE_MAP.containsKey(name);
  }

  public static Set<String> allRuleNames() {
    return Collections.unmodifiableSet(RULE_MAP.keySet());
  }

  public static Map<String, String> unavailableRules() {
    return Collections.unmodifiableMap(UNAVAILABLE_RULES);
  }
}

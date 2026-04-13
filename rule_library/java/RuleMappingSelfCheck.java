package rulecheck;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Validate whether every rule in standard.txt can be resolved from Calcite rule holders.
 *
 * <p>This utility intentionally uses reflection so it can run with different Calcite versions
 * without a hard compile-time dependency on every rule symbol.
 */
public final class RuleMappingSelfCheck {
  private RuleMappingSelfCheck() {}

  public static void main(String[] args) throws IOException {
    if (args.length != 1) {
      System.err.println("Usage: RuleMappingSelfCheck <path_to_standard.txt>");
      System.exit(1);
    }

    if (!hasAnyRuleHolderOnClasspath()) {
      System.err.println(
          "Calcite rule holder classes were not found on the runtime classpath. "
              + "Add calcite-core (and deps) before running this self-check.");
      System.exit(3);
    }

    List<String> ruleNames = loadRuleNames(Path.of(args[0]));
    int ok = 0;
    int missing = 0;

    for (String ruleName : ruleNames) {
      String mapping = resolve(ruleName);
      if (mapping != null) {
        ok++;
        System.out.printf("[OK]      %s -> %s%n", ruleName, mapping);
      } else {
        missing++;
        System.out.printf("[MISSING] %s%n", ruleName);
      }
    }

    System.out.println("\n=== Summary ===");
    System.out.printf("OK: %d%n", ok);
    System.out.printf("MISSING: %d%n", missing);

    if (missing > 0) {
      System.exit(2);
    }
  }

  private static List<String> loadRuleNames(Path path) throws IOException {
    Set<String> dedup = new LinkedHashSet<>();
    for (String rawLine : Files.readAllLines(path)) {
      String line = rawLine.trim();
      if (line.isEmpty() || line.startsWith("#") || line.startsWith("rule_")) {
        continue;
      }
      dedup.add(line);
    }
    return new ArrayList<>(dedup);
  }

  private static boolean hasAnyRuleHolderOnClasspath() {
    String[] owners = {
      "org.apache.calcite.rel.rules.CoreRules",
      "org.apache.calcite.rel.rules.PruneEmptyRules"
    };
    for (String owner : owners) {
      try {
        Class.forName(owner);
        return true;
      } catch (ClassNotFoundException | LinkageError ignored) {
        // Try the next holder.
      }
    }
    return false;
  }

  private static String resolve(String ruleName) {
    String[] owners = {
      "org.apache.calcite.rel.rules.CoreRules",
      "org.apache.calcite.rel.rules.PruneEmptyRules"
    };

    for (String owner : owners) {
      try {
        Class<?> clazz = Class.forName(owner);
        clazz.getField(ruleName).get(null);
        return owner.substring(owner.lastIndexOf('.') + 1) + "." + ruleName;
      } catch (ReflectiveOperationException ignored) {
        // Try the next rule holder.
      }
    }
    return null;
  }
}

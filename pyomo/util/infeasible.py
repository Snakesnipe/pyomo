# -*- coding: UTF-8 -*-
"""Module with diagnostic utilities for infeasible models."""
from pyomo.core import Constraint, Var, value, TraversalStrategy
from math import fabs
import logging

from pyomo.core.expr.visitor import identify_variables

logger = logging.getLogger('pyomo.util.infeasible')
logger.setLevel(logging.INFO)


def log_infeasible_constraints(
        m, tol=1E-6, logger=logger,
        log_expression=False, log_variables=False
):
    """Print the infeasible constraints in the model.

    Uses the current model state. Uses pyomo.util.infeasible logger unless one
    is provided.

    Args:
        m (Block): Pyomo block or model to check
        tol (float): feasibility tolerance
        log_expression (bool): If true, prints the constraint expression
        log_variables (bool): If true, prints the constraint variable names and values

    """
    log_template = "CONSTR {name}: {lhs_value} {operation} {rhs_value}"
    if log_expression:
        log_template += "\n  {lhs_expr} {operation} {rhs_expr}"
    if log_variables:
        log_template += "\n{var_printout}"
    vars_template = "  VAR {name}: {value}"

    # Iterate through all constraints on the model
    for constr in m.component_data_objects(
            ctype=Constraint, active=True, descend_into=True):
        constr_body_value = value(constr.body, exception=False)
        if constr_body_value is None:
            # Undefined constraint body value due to missing variable value
            log_output = 'CONSTR {name}: missing variable value.'.format(name=constr.name)
            if log_variables:
                constraint_vars = identify_variables(constr.body, include_fixed=True)
                log_output += "\n" + '\n'.join(
                    vars_template.format(name=v.name, value=v.value) for v in constraint_vars)
            logger.info(log_output)
            continue
        # if constraint is an equality, handle differently
        if constr.equality and fabs(value(constr.lower - constr.body)) >= tol:
            output_dict = dict(
                name=constr.name, lhs_value=value(constr.body),
                operation="=/=", rhs_value=value(constr.lower))
            if log_expression:
                output_dict['lhs_expr'] = constr.body
                output_dict['rhs_expr'] = constr.lower
            if log_variables:
                constraint_vars = identify_variables(constr.body, include_fixed=True)
                output_dict['var_printout'] = '\n'.join(
                    vars_template.format(name=v.name, value=v.value) for v in constraint_vars)
            logger.info(log_template.format(**output_dict))
            continue
        # otherwise, check LB and UB, if they exist
        if constr.has_lb() and value(constr.lower - constr.body) >= tol:
            output_dict = dict(
                name=constr.name, lhs_value=value(constr.lower),
                operation="</=", rhs_value=value(constr.body))
            if log_expression:
                output_dict['lhs_expr'] = constr.lower
                output_dict['rhs_expr'] = constr.body
            if log_variables:
                constraint_vars = identify_variables(constr.body, include_fixed=True)
                output_dict['var_printout'] = '\n'.join(
                    vars_template.format(name=v.name, value=v.value) for v in constraint_vars)
            logger.info(log_template.format(**output_dict))
        if constr.has_ub() and value(constr.body - constr.upper) >= tol:
            output_dict = dict(
                name=constr.name, lhs_value=value(constr.body),
                operation="</=", rhs_value=value(constr.upper))
            if log_expression:
                output_dict['lhs_expr'] = constr.body
                output_dict['rhs_expr'] = constr.upper
            if log_variables:
                constraint_vars = identify_variables(constr.body, include_fixed=True)
                output_dict['var_printout'] = '\n'.join(
                    vars_template.format(name=v.name, value=v.value) for v in constraint_vars)
            logger.info(log_template.format(**output_dict))


def log_infeasible_bounds(m, tol=1E-6, logger=logger):
    """Print the infeasible variable bounds in the model.

    Args:
        m (Block): Pyomo block or model to check
        tol (float): feasibility tolerance

    """
    for var in m.component_data_objects(
            ctype=Var, descend_into=True):
        var_value = var.value
        if var_value is None:
            logger.debug("Skipping VAR {} with no assigned value.")
            continue
        if var.has_lb() and value(var.lb - var) >= tol:
            logger.info('VAR {}: {} < LB {}'.format(
                var.name, value(var), value(var.lb)))
        if var.has_ub() and value(var - var.ub) >= tol:
            logger.info('VAR {}: {} > UB {}'.format(
                var.name, value(var), value(var.ub)))


def log_close_to_bounds(m, tol=1E-6, logger=logger):
    """Print the variables and constraints that are near their bounds.

    Fixed variables and equality constraints are excluded from this analysis.

    Args:
        m (Block): Pyomo block or model to check
        tol (float): bound tolerance
    """
    for var in m.component_data_objects(
            ctype=Var, descend_into=True):
        if var.fixed:
            continue
        var_value = var.value
        if var_value is None:
            logger.debug("Skipping VAR {} with no assigned value.")
            continue
        if (var.has_lb() and var.has_ub() and
                fabs(value(var.ub - var.lb)) <= 2 * tol):
            continue  # if the bounds are too close, skip.
        if var.has_lb() and fabs(value(var.lb - var)) <= tol:
            logger.info('{} near LB of {}'.format(var.name, value(var.lb)))
        elif var.has_ub() and fabs(value(var.ub - var)) <= tol:
            logger.info('{} near UB of {}'.format(var.name, value(var.ub)))

    for constr in m.component_data_objects(
            ctype=Constraint, descend_into=True, active=True):
        if not constr.equality:
            # skip equality constraints, because they should always be close to
            # bounds if enforced.
            body_value = value(constr.body, exception=False)
            if body_value is None:
                logger.info("Skipping CONSTR {}: missing variable value.".format(constr.name))
                continue
            if (constr.has_ub() and
                    fabs(value(body_value - constr.upper)) <= tol):
                logger.info('{} near UB'.format(constr.name))
            if (constr.has_lb() and
                    fabs(value(body_value - constr.lower)) <= tol):
                logger.info('{} near LB'.format(constr.name))


def log_active_constraints(m, logger=logger):
    """Prints the active constraints in the model."""
    for constr in m.component_data_objects(
        ctype=Constraint, active=True, descend_into=True,
        descent_order=TraversalStrategy.PrefixDepthFirstSearch
    ):
        logger.info("%s active" % constr.name)
